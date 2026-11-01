from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q


class Course(models.Model):
    """Групповой онлайн-курс по снижению веса."""

    class Status(models.TextChoices):
        PAID = "paid", "Платный"
        FREE = "free", "Бесплатный"

    class State(models.TextChoices):
        OPEN = "open", "Открыт для записи"
        RUNNING = "running", "Идёт"
        ARCHIVED = "archived", "Архивный"

    # Free course lasts one week, paid course lasts four weeks
    DURATION = {Status.FREE: timedelta(weeks=1), Status.PAID: timedelta(weeks=4)}

    name = models.CharField("Название", max_length=255)
    status = models.CharField("Статус курса", max_length=8, choices=Status.choices)
    price = models.DecimalField(
        "Цена", max_digits=10, decimal_places=2, null=True, blank=True
    )
    start_at = models.DateTimeField("Время начала")
    end_at = models.DateTimeField("Время окончания")
    state = models.CharField(
        "Состояние", max_length=8, choices=State.choices, default=State.OPEN
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "курс"
        verbose_name_plural = "курсы"
        ordering = ["start_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status="free", price__isnull=True)
                | Q(status="paid", price__gt=0),
                name="course_price_matches_status",
            ),
            models.CheckConstraint(
                condition=Q(end_at__gt=models.F("start_at")),
                name="course_ends_after_start",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_paid(self):
        return self.status == self.Status.PAID

    @classmethod
    def end_for(cls, status, start_at):
        return start_at + cls.DURATION[status]


class Participant(models.Model):
    """Участие пользователя в курсе (сущность «Участник курса»)."""

    class Method(models.TextChoices):
        SELF = "self", "Самостоятельно"
        MANUAL = "manual", "Вручную администратором"

    class Status(models.TextChoices):
        ACTIVE = "active", "Активен"
        EXCLUDED = "excluded", "Исключён"

    class Reason(models.TextChoices):
        REQUEST = "request", "Заявка участника"
        VIOLATION = "violation", "Нарушение правил"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="participations",
        verbose_name="Пользователь",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="participants",
        verbose_name="Курс",
    )
    enrolled_at = models.DateTimeField("Дата зачисления", auto_now_add=True)
    method = models.CharField("Способ зачисления", max_length=8, choices=Method.choices)
    status = models.CharField(
        "Статус участия", max_length=8, choices=Status.choices, default=Status.ACTIVE
    )
    exclusion_reason = models.CharField(
        "Причина исключения", max_length=16, choices=Reason.choices, blank=True
    )

    class Meta:
        verbose_name = "участник курса"
        verbose_name_plural = "участники курса"
        ordering = ["enrolled_at", "pk"]
        constraints = [
            # A user may enrol again after exclusion, but only one active participation
            models.UniqueConstraint(
                fields=["user", "course"],
                condition=Q(status="active"),
                name="one_active_participation_per_course",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.course}"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class Payment(models.Model):
    """Оплата платного курса. Сохраняется только после подтверждения оплаты."""

    class Method(models.TextChoices):
        SERVICE = "service", "Через платёжный сервис"
        OFFLINE = "offline", "Вне системы"

    participant = models.OneToOneField(
        Participant,
        on_delete=models.PROTECT,
        related_name="payment",
        verbose_name="Участник курса",
    )
    method = models.CharField("Способ оплаты", max_length=8, choices=Method.choices)
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField("Дата оплаты")
    transaction_id = models.CharField("ID транзакции", max_length=64, blank=True)

    class Meta:
        verbose_name = "платёж"
        verbose_name_plural = "платежи"
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payment_amount_positive"
            ),
        ]

    def __str__(self):
        return f"{self.participant}: {self.amount}"

    @property
    def is_offline(self):
        return self.method == self.Method.OFFLINE


class ExclusionRequest(models.Model):
    """Заявка на исключение из курса и возврат средств."""

    class Basis(models.TextChoices):
        PARTICIPANT = "participant", "Заявка участника"
        VIOLATION = "violation", "Нарушение правил"

    class Status(models.TextChoices):
        REGISTERED = "registered", "Зарегистрирована"
        DONE = "done", "Выполнена"
        REJECTED = "rejected", "Отклонена"

    participant = models.ForeignKey(
        Participant,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name="Участник курса",
    )
    # Fixed at creation: the refund deadline is counted from this moment
    created_at = models.DateTimeField(
        "Дата и время подачи", auto_now_add=True, editable=False
    )
    basis = models.CharField("Основание", max_length=12, choices=Basis.choices)
    reason = models.TextField("Причина", blank=True)
    status = models.CharField(
        "Статус", max_length=12, choices=Status.choices, default=Status.REGISTERED
    )

    class Meta:
        verbose_name = "заявка на исключение"
        verbose_name_plural = "заявки на исключение"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["participant"],
                condition=Q(status="registered"),
                name="one_registered_request_per_participant",
            ),
        ]

    def __str__(self):
        return f"Заявка №{self.pk} ({self.participant})"


class Refund(models.Model):
    """Возврат средств. Сохраняется только после подтверждения возврата."""

    request = models.OneToOneField(
        ExclusionRequest,
        on_delete=models.PROTECT,
        related_name="refund",
        verbose_name="Заявка",
    )
    amount = models.DecimalField("Сумма возврата", max_digits=10, decimal_places=2)
    fpr = models.DecimalField(
        "Фактически понесённые расходы", max_digits=10, decimal_places=2
    )
    refunded_at = models.DateTimeField("Дата возврата", auto_now_add=True)

    class Meta:
        verbose_name = "возврат средств"
        verbose_name_plural = "возвраты средств"
        constraints = [
            models.CheckConstraint(
                condition=Q(fpr__gte=0), name="refund_fpr_not_negative"
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="refund_amount_not_negative"
            ),
        ]

    def __str__(self):
        return f"Возврат по заявке №{self.request_id}: {self.amount}"
