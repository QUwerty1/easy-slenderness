from datetime import date
from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from course.models import Course, Participant
from course.views import CourseAPIView

from . import services
from .models import PHOTO_CONTENT_TYPES, HomeworkReport, MealEntry, MealPhoto
from .serializers import (
    HomeworkReportSerializer,
    MealCreateSerializer,
    MealEntrySerializer,
    MealUpdateSerializer,
    ParticipantCommentSerializer,
    ReviewSerializer,
)


def parse_report_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise services.HomeworkError("Некорректная дата.", "invalid_date") from None


class HomeworkAPIView(CourseAPIView):
    def get_course(self, course_id):
        return get_object_or_404(Course, pk=course_id)

    def check_participant_or_tutor(self, request, course):
        if services.is_tutor(request.user):
            return None
        services.ensure_learner(request.user)
        return services.get_active_participant(request.user, course)


class ReportListView(HomeworkAPIView):
    def get(self, request, course_id):
        course = self.get_course(course_id)
        participant = self.check_participant_or_tutor(request, course)
        if participant is not None:
            return Response(
                {
                    "mode": "participant",
                    "course_id": course.pk,
                    "course_name": course.name,
                    "days": services.participant_report_list(participant, course),
                }
            )
        return Response(
            {
                "mode": "tutor",
                "course_id": course.pk,
                "course_name": course.name,
                **services.tutor_report_grid(course),
            }
        )


class ReportDateView(HomeworkAPIView):
    def get(self, request, course_id, report_date):
        course = self.get_course(course_id)
        day = parse_report_date(report_date)

        participant = self.check_participant_or_tutor(request, course)
        if participant is None:
            participant_id = request.query_params.get("participant_id")
            if not participant_id:
                return Response({"detail": "Не указан участник курса."}, status=400)
            participant = get_object_or_404(
                Participant.objects.select_related("user", "course"),
                pk=participant_id,
                course=course,
            )
        services.sync_expired_reports(course)
        state = services.report_window(course, day)
        report = (
            HomeworkReport.objects.filter(participant=participant, report_date=day)
            .prefetch_related("meals__photos")
            .first()
        )

        if state == "unavailable":
            return Response(
                {
                    "available": False,
                    "is_created": report is not None,
                    "report_date": day,
                    "message": "Отчет пока недоступен для заполнения.",
                }
            )
        if report is None:
            if state == "closed":
                return Response(
                    {
                        "available": False,
                        "is_created": False,
                        "report_date": day,
                        "status": "not_completed",
                        "message": "Отчет за эту дату не был создан. День отмечен как невыполненный.",
                    }
                )
            return Response(
                {
                    "available": True,
                    "is_created": False,
                    "report_date": day,
                    "status": "filling",
                    "status_display": "Заполняется",
                    "participant_comment": "",
                    "tutor_comment": "",
                    "is_completed": None,
                    "meal_count": 0,
                    "meals": [],
                }
            )
        data = HomeworkReportSerializer(report, context={"request": request}).data
        data["available"] = (
            state == "open"
            and report.status == HomeworkReport.Status.FILLING
            and not services.is_tutor(request.user)
        )
        data["is_created"] = True
        data["participant_name"] = participant.user.full_name
        return Response(data)

    def patch(self, request, course_id, report_date):
        course = self.get_course(course_id)
        participant = self.check_participant_or_tutor(request, course)
        if participant is None:
            return Response(
                {"detail": "Тьютор не может изменять комментарий участника."},
                status=403,
            )
        day = parse_report_date(report_date)
        serializer = ParticipantCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = services.save_participant_comment(
            participant,
            course,
            day,
            serializer.validated_data["participant_comment"],
        )
        return Response(
            HomeworkReportSerializer(report, context={"request": request}).data
        )


class MealCreateView(HomeworkAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, course_id, report_date):
        course = self.get_course(course_id)
        participant = self.check_participant_or_tutor(request, course)
        if participant is None:
            return Response(
                {"detail": "Тьютор не может добавлять приемы пищи."}, status=403
            )
        day = parse_report_date(report_date)
        # Cheap checks first: do not decode uploaded images for a closed report.
        if services.report_window(course, day) != "open":
            raise services.HomeworkError(
                "Заполнять отчет можно только за текущую дату.", "report_closed", 409
            )
        serializer = MealCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        report, _ = services.add_meal(
            participant,
            course,
            day,
            data,
            data["photos"],
        )
        return Response(
            HomeworkReportSerializer(report, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class MealDetailView(HomeworkAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, course_id, meal_id):
        course = self.get_course(course_id)
        participant = self.check_participant_or_tutor(request, course)
        if participant is None:
            return Response(
                {"detail": "Тьютор не может изменять приемы пищи."}, status=403
            )
        meal = get_object_or_404(
            MealEntry.objects.select_related("report__participant"),
            pk=meal_id,
            report__participant=participant,
        )
        serializer = MealUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_meal(
            participant,
            course,
            meal,
            serializer.validated_data,
            serializer.validated_data.get("photos"),
        )
        meal.refresh_from_db()
        return Response(
            {"meal": MealEntrySerializer(meal, context={"request": request}).data}
        )


class TutorReviewView(HomeworkAPIView):
    def post(self, request, course_id, report_id):
        course = self.get_course(course_id)
        services.ensure_tutor(request.user)
        report = get_object_or_404(
            HomeworkReport.objects.select_related("participant__course"),
            pk=report_id,
            participant__course=course,
        )
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = services.review_report(
            report,
            serializer.validated_data["tutor_comment"],
            serializer.validated_data["is_completed"],
        )
        return Response(
            HomeworkReportSerializer(report, context={"request": request}).data
        )


class MealPhotoView(APIView):
    def get(self, request, photo_id):
        photo = get_object_or_404(
            MealPhoto.objects.select_related("meal__report__participant__user"),
            pk=photo_id,
        )
        report = photo.meal.report
        is_tutor = services.is_tutor(request.user)
        is_owner = report.participant.user_id == request.user.pk
        if not (is_tutor or is_owner):
            return Response({"detail": "Нет доступа к фотографии."}, status=403)
        try:
            photo.image.open("rb")
        except OSError, ValueError:
            raise Http404("Файл фотографии не найден.") from None
        filename = Path(photo.image.name).name
        content_type = PHOTO_CONTENT_TYPES.get(Path(filename).suffix.lower())
        # Inline отдаются только проверенные растровые форматы; остальное
        # (например, файлы, загруженные до проверки) — как вложение.
        response = FileResponse(
            photo.image,
            as_attachment=content_type is None,
            filename=filename,
            content_type=content_type or "application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "sandbox; default-src 'none'"
        return response
