import io
import random
from datetime import datetime, time, timedelta
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image

from course.models import Course, Participant
from homework import services
from homework.models import HomeworkReport, MealEntry
from homework.serializers import ImageFileField

PLACEHOLDER_PATH = Path(__file__).with_name("favicon.ico")

COMMENTS = [
    "",
    "Самочувствие хорошее.",
    "Старался придерживаться рекомендаций.",
    "День прошёл продуктивно.",
    "Выполнил рекомендации по питанию.",
]


def load_placeholder():
    """favicon.ico → PNG: загрузка фото принимает только JPEG, PNG и WebP."""
    if not PLACEHOLDER_PATH.exists():
        raise CommandError(f"Не найден файл заглушки: {PLACEHOLDER_PATH}")
    buffer = io.BytesIO()
    with Image.open(PLACEHOLDER_PATH) as image:
        image.save(buffer, format="PNG")
    return buffer.getvalue()


def placeholder_photo(content):
    """Новый файл фото, прошедший ту же проверку, что и загрузка через API."""
    upload = SimpleUploadedFile("favicon.png", content, content_type="image/png")
    return ImageFileField().to_internal_value(upload)


def moment_in_day(course, report_date):
    """Момент дня отчета, когда отчет открыт для заполнения, или None."""
    tz = timezone.get_current_timezone()
    moment = timezone.make_aware(datetime.combine(report_date, time(20, 0)), tz)
    moment = max(moment, course.start_at)
    moment = min(moment, course.end_at - timedelta(minutes=1))
    if timezone.localdate(moment) != report_date:
        return None
    return moment


def end_of_day(report_date):
    """Начало следующего дня: в этот момент отчет уходит на проверку."""
    tz = timezone.get_current_timezone()
    return timezone.make_aware(
        datetime.combine(report_date + timedelta(days=1), time.min), tz
    )


class Command(BaseCommand):
    help = (
        "Создаёт демонстрационные отчёты по ДЗ за прошедшие дни текущих курсов "
        "по тем же правилам, что и API: приемы пищи с фото-заглушкой (favicon.ico) "
        "добавляются в день отчета, затем отчет отправляется на проверку."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--probability",
            type=int,
            default=70,
            help="Вероятность создания отчёта для одного участника за один день (0–100).",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Начальное значение генератора случайных чисел.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, какие отчёты будут созданы, без записи в БД.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        probability = options["probability"]
        dry_run = options["dry_run"]
        if not 0 <= probability <= 100:
            raise CommandError("Вероятность должна быть от 0 до 100.")

        placeholder = load_placeholder()
        rng = random.Random(options["seed"])
        now = timezone.now()
        today = timezone.localdate(now)

        # Курсы, которые уже начались, но ещё не закончились.
        courses = Course.objects.filter(start_at__lte=now, end_at__gt=now).order_by(
            "pk"
        )

        created_reports = 0
        created_meals = 0
        skipped_reports = 0

        for course in courses:
            participants = Participant.objects.filter(
                course=course, status=Participant.Status.ACTIVE
            ).select_related("user")
            past_dates = [d for d in services.course_dates(course) if d < today]
            if not past_dates:
                continue

            self.stdout.write(
                f"\nКурс: {course.name}; "
                f"участников: {participants.count()}; "
                f"прошедших дней: {len(past_dates)}"
            )

            for participant in participants:
                for report_date in past_dates:
                    if rng.randint(1, 100) > probability:
                        continue
                    if HomeworkReport.objects.filter(
                        participant=participant, report_date=report_date
                    ).exists():
                        skipped_reports += 1
                        continue
                    filled_at = moment_in_day(course, report_date)
                    if filled_at is None:
                        continue

                    meal_count = rng.randint(2, 4)
                    if not dry_run:
                        self.fill_report(
                            participant,
                            course,
                            report_date,
                            filled_at,
                            meal_count,
                            placeholder,
                            rng,
                        )
                    created_reports += 1
                    created_meals += meal_count
                    self.stdout.write(
                        f"  Отчет: {participant.user.full_name}, "
                        f"{report_date}, приемов пищи: {meal_count}"
                    )

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.WARNING("Режим предварительного просмотра. БД не изменена.")
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Создано отчетов: {created_reports}\n"
                f"Создано приемов пищи: {created_meals}\n"
                f"Пропущено существующих отчетов: {skipped_reports}"
            )
        )

    def fill_report(
        self, participant, course, report_date, filled_at, meal_count, placeholder, rng
    ):
        """Заполняет отчет так же, как участник через API, и закрывает день."""
        for _ in range(meal_count):
            services.add_meal(
                participant,
                course,
                report_date,
                {
                    "water_drank": rng.choice([True, False]),
                    "breathing_practice": rng.choice([True, False]),
                    "feeling": rng.choice(MealEntry.Feeling.values),
                },
                [placeholder_photo(placeholder)],
                now=filled_at,
            )
        comment = rng.choice(COMMENTS)
        if comment:
            services.save_participant_comment(
                participant, course, report_date, comment, now=filled_at
            )
        # Конец дня: отчет переходит в «Проверяется», как при запуске по расписанию.
        services.sync_expired_reports(course, now=end_of_day(report_date))
