import uuid
from pathlib import Path

from django.db import models
from django.db.models import Q
from django.utils import timezone

from course.models import Participant


class HomeworkReport(models.Model):
    """Ежедневный отчет участника о выполнении единственного ДЗ."""

    class Status(models.TextChoices):
        FILLING = "filling", "Заполняется"
        REVIEW = "review", "Проверяется"
        REVIEWED = "reviewed", "Проверен"

    participant = models.ForeignKey(
        Participant,
        on_delete=models.PROTECT,
        related_name="homework_reports",
        verbose_name="Участник курса",
    )
    report_date = models.DateField("Дата отчета")
    status = models.CharField(
        "Статус",
        max_length=12,
        choices=Status.choices,
        default=Status.FILLING,
    )
    participant_comment = models.TextField("Комментарий участника", blank=True)
    tutor_comment = models.TextField("Комментарий тьютора", blank=True)
    is_completed = models.BooleanField(
        "Выполнено",
        null=True,
        blank=True,
        help_text="Заполняется тьютором при проверке.",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Изменен", auto_now=True)
    submitted_at = models.DateTimeField("Отправлен на проверку", null=True, blank=True)
    reviewed_at = models.DateTimeField("Проверен", null=True, blank=True)

    class Meta:
        verbose_name = "отчет по домашнему заданию"
        verbose_name_plural = "отчеты по домашним заданиям"
        ordering = ["report_date", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "report_date"],
                name="one_homework_report_per_participant_day",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="reviewed", is_completed__isnull=False)
                    | ~Q(status="reviewed")
                ),
                name="homework_reviewed_has_grade",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "report_date"], name="homework_h_status_7acb11_idx"
            ),
        ]

    def __str__(self):
        return f"Отчет {self.participant_id} за {self.report_date}"


class MealEntry(models.Model):
    """Один прием пищи в ежедневном отчете."""

    class Feeling(models.TextChoices):
        HUNGER = "hunger", "Голод"
        APPETITE = "appetite", "Аппетит"

    report = models.ForeignKey(
        HomeworkReport,
        on_delete=models.CASCADE,
        related_name="meals",
        verbose_name="Отчет",
    )
    water_drank = models.BooleanField("Выпит стакан воды")
    breathing_practice = models.BooleanField("Выполнена дыхательная практика")
    feeling = models.CharField(
        "Ощущение перед приемом", max_length=8, choices=Feeling.choices
    )
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)
    updated_at = models.DateTimeField("Изменен", auto_now=True)

    class Meta:
        verbose_name = "прием пищи"
        verbose_name_plural = "приемы пищи"
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"Прием пищи №{self.pk} ({self.report.report_date})"


# Разрешенные форматы фото: формат Pillow → (расширение, Content-Type).
PHOTO_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}
PHOTO_CONTENT_TYPES = dict(PHOTO_FORMATS.values())


def meal_photo_upload_to(instance, filename):
    """Случайное имя файла: исходное имя пользователя не сохраняется.

    Расширение уже приведено к проверенному формату в ImageFileField.
    """
    ext = Path(filename).suffix.lower()
    if ext not in PHOTO_CONTENT_TYPES:
        ext = ".bin"
    return f"homework/meals/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class MealPhoto(models.Model):
    """Фотография блюда, прикрепленная к приему пищи."""

    meal = models.ForeignKey(
        MealEntry,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="Прием пищи",
    )
    image = models.FileField("Фото блюда", upload_to=meal_photo_upload_to)
    uploaded_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        verbose_name = "фото блюда"
        verbose_name_plural = "фотографии блюд"

    def __str__(self):
        return f"Фото №{self.pk} к приему пищи №{self.meal_id}"
