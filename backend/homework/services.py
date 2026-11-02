from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from authorization.models import User
from course.models import Participant
from course.services import CourseError, is_learner

from .models import HomeworkReport, MealEntry, MealPhoto


class HomeworkError(CourseError):
    """Homework rule violation; rendered by ``CourseAPIView`` like ``CourseError``."""


def course_dates(course):
    """Возвращает календарные дни курса; end_at является исключающей границей."""
    start_date = timezone.localtime(course.start_at).date()
    duration = course.end_at - course.start_at
    days = max(1, int(duration.total_seconds() // 86400))
    return [start_date + timedelta(days=i) for i in range(days)]


def report_window(course, report_date, now=None):
    now = now or timezone.now()
    local_now = timezone.localtime(now)
    dates = course_dates(course)
    if report_date not in dates:
        raise HomeworkError(
            "Выбранная дата не входит в период проведения курса.", "invalid_date", 404
        )

    today = local_now.date()
    if report_date > today:
        return "unavailable"
    if report_date < today:
        return "closed"
    if now < course.start_at or now >= course.end_at:
        return "unavailable"
    return "open"


def get_active_participant(user, course):
    participant = (
        Participant.objects.filter(
            user=user, course=course, status=Participant.Status.ACTIVE
        )
        .select_related("user", "course")
        .first()
    )
    if participant is None:
        raise HomeworkError(
            "Вы не являетесь активным участником этого курса.", "forbidden", 403
        )
    return participant


def is_tutor(user):
    return user.is_authenticated and user.role == User.Role.TUTOR


def ensure_tutor(user):
    if not is_tutor(user):
        raise HomeworkError("Действие доступно только тьютору.", "forbidden", 403)


def ensure_learner(user):
    if not is_learner(user):
        raise HomeworkError(
            "Действие доступно только участнику курса.", "forbidden", 403
        )


def sync_expired_reports(course=None, now=None):
    """Закрывает отчеты предыдущих календарных дней, если задача планировщика задержалась."""
    today = timezone.localdate(now or timezone.now())
    qs = HomeworkReport.objects.filter(
        status=HomeworkReport.Status.FILLING,
        report_date__lt=today,
    )
    if course is not None:
        qs = qs.filter(participant__course=course)
    return qs.update(
        status=HomeworkReport.Status.REVIEW,
        submitted_at=now or timezone.now(),
    )


def participant_report_list(participant, course, now=None):
    now = now or timezone.now()
    sync_expired_reports(course, now)
    reports = {
        report.report_date: report
        for report in HomeworkReport.objects.filter(
            participant=participant
        ).prefetch_related("meals")
    }
    today = timezone.localdate(now)
    result = []
    for day in course_dates(course):
        report = reports.get(day)
        if report:
            result.append(
                {
                    "date": day,
                    "report_id": report.pk,
                    "is_created": True,
                    "available": report_window(course, day, now) == "open"
                    and report.status == HomeworkReport.Status.FILLING,
                    "status": report.status,
                    "status_display": report.get_status_display(),
                    "is_completed": report.is_completed,
                    "meal_count": report.meals.count(),
                }
            )
        elif (
            day > today
            or report_window(course, day, now) == "unavailable"
            and day >= today
        ):
            result.append(
                {
                    "date": day,
                    "report_id": None,
                    "is_created": False,
                    "available": False,
                    "status": "unavailable",
                    "status_display": "Недоступен",
                    "is_completed": None,
                    "meal_count": 0,
                }
            )
        elif day == today:
            result.append(
                {
                    "date": day,
                    "report_id": None,
                    "is_created": False,
                    "available": True,
                    "status": HomeworkReport.Status.FILLING,
                    "status_display": "Заполняется",
                    "is_completed": None,
                    "meal_count": 0,
                }
            )
        else:
            result.append(
                {
                    "date": day,
                    "report_id": None,
                    "is_created": False,
                    "available": False,
                    "status": "not_completed",
                    "status_display": "Не выполнено",
                    "is_completed": None,
                    "meal_count": 0,
                }
            )
    return result


def get_or_create_report(participant, course, report_date, now=None):
    now = now or timezone.now()
    if report_window(course, report_date, now) != "open":
        raise HomeworkError(
            "Заполнять отчет можно только за текущую дату.", "report_closed", 409
        )
    with transaction.atomic():
        # Lock the participation row to serialize simultaneous first submissions.
        Participant.objects.select_for_update().get(pk=participant.pk)
        report, _ = HomeworkReport.objects.get_or_create(
            participant=participant,
            report_date=report_date,
            defaults={"status": HomeworkReport.Status.FILLING},
        )
        if report.status != HomeworkReport.Status.FILLING:
            raise HomeworkError(
                "Время заполнения отчета истекло.", "report_closed", 409
            )
        return report


def add_meal(participant, course, report_date, data, photos, now=None):
    if not photos:
        raise HomeworkError(
            "Прикрепите хотя бы одну фотографию блюда.", "photos_required"
        )
    if (
        data.get("water_drank") is None
        or data.get("breathing_practice") is None
        or not data.get("feeling")
    ):
        raise HomeworkError(
            "Заполните все отметки о приеме пищи.", "meal_fields_required"
        )
    with transaction.atomic():
        report = get_or_create_report(participant, course, report_date, now)
        meal = MealEntry.objects.create(
            report=report,
            water_drank=data["water_drank"],
            breathing_practice=data["breathing_practice"],
            feeling=data["feeling"],
        )
        for photo in photos:
            MealPhoto.objects.create(meal=meal, image=photo)
    return report, meal


def update_meal(participant, course, meal, data, photos=None, now=None):
    report = meal.report
    if report.participant_id != participant.pk:
        raise HomeworkError("Нет доступа к этому приему пищи.", "forbidden", 403)
    if (
        report_window(course, report.report_date, now) != "open"
        or report.status != HomeworkReport.Status.FILLING
    ):
        raise HomeworkError(
            "Редактирование отчета уже недоступно.", "report_closed", 409
        )
    if not data.get("feeling"):
        raise HomeworkError(
            "Заполните ощущение перед приемом пищи.", "meal_fields_required"
        )
    with transaction.atomic():
        meal.water_drank = data["water_drank"]
        meal.breathing_practice = data["breathing_practice"]
        meal.feeling = data["feeling"]
        meal.save(
            update_fields=["water_drank", "breathing_practice", "feeling", "updated_at"]
        )
        if photos is not None:
            old_photos = list(meal.photos.all())
            for photo in photos:
                MealPhoto.objects.create(meal=meal, image=photo)
            for old_photo in old_photos:
                old_photo.delete()
            # Files are removed only after the commit: a rollback keeps the old photos intact.
            old_files = [p.image for p in old_photos]
            transaction.on_commit(
                lambda: [image.delete(save=False) for image in old_files]
            )
    return meal


def save_participant_comment(participant, course, report_date, comment, now=None):
    if report_window(course, report_date, now) != "open":
        raise HomeworkError(
            "Комментарий можно оставить только в день заполнения отчета.",
            "report_closed",
            409,
        )
    report = HomeworkReport.objects.filter(
        participant=participant, report_date=report_date
    ).first()
    if report is None or not report.meals.exists():
        raise HomeworkError(
            "Сначала добавьте хотя бы один прием пищи.", "meal_required", 409
        )
    if report.status != HomeworkReport.Status.FILLING:
        raise HomeworkError("Время заполнения отчета истекло.", "report_closed", 409)
    report.participant_comment = comment
    report.save(update_fields=["participant_comment", "updated_at"])
    return report


def tutor_report_grid(course, now=None):
    now = now or timezone.now()
    sync_expired_reports(course, now)
    participants = list(
        course.participants.filter(status=Participant.Status.ACTIVE)
        .select_related("user")
        .order_by("user__full_name", "pk")
    )
    reports = HomeworkReport.objects.filter(
        participant__course=course,
        status__in=[HomeworkReport.Status.REVIEW, HomeworkReport.Status.REVIEWED],
    ).prefetch_related("meals")
    report_map = {(r.participant_id, r.report_date): r for r in reports}
    today = timezone.localdate(now)
    dates = [d for d in course_dates(course) if d <= today]
    rows = []
    for participant in participants:
        cells = []
        enrolled_on = timezone.localdate(participant.enrolled_at)
        for day in dates:
            report = report_map.get((participant.pk, day))
            if report:
                cells.append(
                    {
                        "date": day,
                        "report_id": report.pk,
                        "status": report.status,
                        "status_display": report.get_status_display(),
                        "is_completed": report.is_completed,
                        "meal_count": report.meals.count(),
                    }
                )
            elif enrolled_on <= day < today:
                cells.append(
                    {
                        "date": day,
                        "report_id": None,
                        "status": HomeworkReport.Status.REVIEWED,
                        "status_display": "Проверен",
                        "is_completed": False,
                        "meal_count": 0,
                    }
                )
            else:
                # Today is still being filled, and days before enrollment are not missed.
                cells.append(None)
        rows.append(
            {
                "participant_id": participant.pk,
                "participant_name": participant.user.full_name,
                "cells": cells,
            }
        )
    return {"dates": dates, "participants": rows}


def review_report(report, tutor_comment, is_completed, now=None):
    if report.status != HomeworkReport.Status.REVIEW:
        raise HomeworkError(
            "Можно проверять только отчеты со статусом «Проверяется».",
            "invalid_status",
            409,
        )
    report.tutor_comment = tutor_comment
    report.is_completed = is_completed
    report.status = HomeworkReport.Status.REVIEWED
    report.reviewed_at = now or timezone.now()
    report.save(
        update_fields=[
            "tutor_comment",
            "is_completed",
            "status",
            "reviewed_at",
            "updated_at",
        ]
    )
    return report
