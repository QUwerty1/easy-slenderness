"""Business logic of the course management module.

Views stay thin: every rule from the functional requirements is checked here and
reported with ``CourseError`` (message for the user + machine-readable code).
"""

from datetime import datetime, time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Course, ExclusionRequest, Participant, Payment, Refund
from .payments import GatewayError, get_gateway, make_order_id, parse_order_id

User = get_user_model()

LEARNER_ROLES = (User.Role.USER, User.Role.PARTICIPANT)


class CourseError(Exception):
    def __init__(self, message, code="invalid", status=400, field=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.field = field


# ---------- Роли ----------


def is_admin(user):
    return user.is_authenticated and user.role == User.Role.ADMIN


def is_tutor(user):
    return user.is_authenticated and user.role == User.Role.TUTOR


def is_learner(user):
    return user.is_authenticated and user.role in LEARNER_ROLES


def sync_role(user):
    """«Участник курса» while the user has an active participation, else «Пользователь»."""
    if user.role not in LEARNER_ROLES:
        return
    has_active = user.participations.filter(status=Participant.Status.ACTIVE).exists()
    role = User.Role.PARTICIPANT if has_active else User.Role.USER
    if user.role != role:
        user.role = role
        user.save(update_fields=["role"])


# ---------- Курсы ----------


def update_states(now=None):
    """Signal of the system timer: open → running at start, running → archived at end."""
    now = now or timezone.now()
    started = Course.objects.filter(state=Course.State.OPEN, start_at__lte=now).update(
        state=Course.State.RUNNING
    )
    archived = Course.objects.filter(
        state__in=[Course.State.OPEN, Course.State.RUNNING], end_at__lte=now
    ).update(state=Course.State.ARCHIVED)
    return started, archived


def is_open_for_enrollment(course, now=None):
    now = now or timezone.now()
    return course.state == Course.State.OPEN and course.start_at > now


def is_archived(course, now=None):
    now = now or timezone.now()
    return course.state == Course.State.ARCHIVED or course.end_at <= now


def _validate_course_data(name, status, price, start_at):
    if not (name or "").strip():
        raise CourseError("Название не может быть пустым.", field="name")
    if start_at < timezone.now():
        raise CourseError(
            "Время начала не может быть раньше текущего момента.", field="start_at"
        )
    if status == Course.Status.PAID and (price is None or price <= 0):
        raise CourseError(
            "Для платного курса цена должна быть больше нуля.", field="price"
        )


def create_course(name, status, start_at, price=None):
    price = price if status == Course.Status.PAID else None
    _validate_course_data(name, status, price, start_at)
    return Course.objects.create(
        name=name.strip(),
        status=status,
        price=price,
        start_at=start_at,
        end_at=Course.end_for(status, start_at),
    )


def can_edit(course):
    return is_open_for_enrollment(course)


def update_course(course, name=None, start_at=None, price=None):
    if not can_edit(course):
        raise CourseError(
            "Курс уже начался: редактирование запрещено.", "course_started", 409
        )
    name = course.name if name is None else name
    start_at = course.start_at if start_at is None else start_at
    price = (course.price if price is None else price) if course.is_paid else None
    _validate_course_data(name, course.status, price, start_at)
    course.name = name.strip()
    course.start_at = start_at
    course.end_at = Course.end_for(course.status, start_at)
    course.price = price
    course.save()
    return course


def available_courses():
    return Course.objects.filter(state=Course.State.OPEN, start_at__gt=timezone.now())


def my_courses(user):
    if is_tutor(user):
        return Course.objects.all()
    return Course.objects.filter(
        participants__user=user, participants__status=Participant.Status.ACTIVE
    ).distinct()


def active_participant(user, course):
    return course.participants.filter(
        user=user, status=Participant.Status.ACTIVE
    ).first()


def can_view_course(user, course):
    """Course page: active participants, tutors and the administrator."""
    if is_admin(user) or is_tutor(user):
        return True
    return active_participant(user, course) is not None


def can_view_card(user, course):
    """Course card from the list of available courses."""
    return can_view_course(user, course) or is_open_for_enrollment(course)


# ---------- Запись на курс и оплата ----------


def check_can_enroll(user, course):
    if not is_learner(user):
        raise CourseError(
            "Записаться на курс может только пользователь.", "forbidden", 403
        )
    if not is_open_for_enrollment(course):
        raise CourseError(
            "Запись на курс закрыта: курс уже начался.", "enrollment_closed", 409
        )
    if active_participant(user, course):
        raise CourseError("Вы уже записаны на этот курс.", "already_participant", 409)


def _add_participant(user, course, method):
    try:
        with transaction.atomic():
            participant = Participant.objects.create(
                user=user, course=course, method=method
            )
    except IntegrityError as exc:
        raise CourseError(
            "Вы уже записаны на этот курс.", "already_participant", 409
        ) from exc
    sync_role(user)
    return participant


def enroll(user, course, consents):
    """Free course: participant at once. Paid course: URL of the payment page."""
    check_can_enroll(user, course)
    if not course.is_paid:
        participant = _add_participant(user, course, Participant.Method.SELF)
        return {"result": "enrolled", "participant_id": participant.pk}
    if not all(consents.get(key) for key in ("offer", "refund_policy", "pd")):
        raise CourseError(
            "Для оплаты нужно принять договор оферты, политику возврата средств "
            "и дать согласие на обработку персональных данных.",
            "consent_required",
        )
    return_url = f"{settings.FRONTEND_URL}/payment/return?course={course.pk}"
    try:
        url = get_gateway().create_payment(
            make_order_id(user.pk, course.pk),
            f"Оплата курса «{course.name}»",
            course.price,
            return_url,
        )
    except GatewayError as exc:
        raise CourseError(str(exc), "gateway_error", 502) from exc
    return {"result": "payment", "payment_url": url}


def confirm_payment(result):
    """Notification from the payment service with the order id.

    Returns the created participant or ``None`` when nobody is enrolled: the payment
    failed, or it came when the user is already an active participant or the
    course has started. Such payments are returned by the administrator in the
    payment service account (external process) and are not saved by the module.
    """
    if not result.succeeded:
        return None
    parsed = parse_order_id(result.order_id)
    if parsed is None:
        return None
    user = User.objects.filter(pk=parsed[0]).first()
    course = Course.objects.filter(pk=parsed[1]).first()
    if user is None or course is None:
        return None
    try:
        check_can_enroll(user, course)
    except CourseError:
        return None
    with transaction.atomic():
        participant = _add_participant(user, course, Participant.Method.SELF)
        Payment.objects.create(
            participant=participant,
            method=Payment.Method.SERVICE,
            amount=result.amount or course.price,
            paid_at=timezone.now(),
            transaction_id=result.transaction_id,
        )
    return participant


# ---------- Ручное зачисление ----------


def candidates(course, full_name="", phone="", email=""):
    users = User.objects.filter(role__in=LEARNER_ROLES, status=User.Status.ACTIVE)
    if full_name:
        users = users.filter(full_name__icontains=full_name.strip())
    if phone:
        digits = "".join(ch for ch in phone if ch.isdigit())
        users = users.filter(phone__contains=digits)
    if email:
        users = users.filter(email__icontains=email.strip())
    return users.order_by("full_name")


def manual_enroll(course, user, amount, paid_on):
    if not course.is_paid:
        raise CourseError("Ручное зачисление доступно только на платный курс.")
    if not is_open_for_enrollment(course):
        raise CourseError(
            "Курс уже начался: зачисление возможно только до его начала.",
            "enrollment_closed",
            409,
        )
    if not is_learner(user) or not user.is_active:
        raise CourseError("Зачислить можно только зарегистрированного пользователя.")
    if active_participant(user, course):
        raise CourseError(
            "Пользователь уже является участником этого курса.",
            "already_participant",
            409,
        )
    if amount is None or amount <= 0:
        raise CourseError("Сумма оплаты должна быть больше нуля.", field="amount")
    if paid_on > timezone.localdate():
        raise CourseError(
            "Дата оплаты не может быть позже текущей даты.", field="paid_on"
        )
    with transaction.atomic():
        participant = _add_participant(user, course, Participant.Method.MANUAL)
        Payment.objects.create(
            participant=participant,
            method=Payment.Method.OFFLINE,
            amount=amount,
            paid_at=timezone.make_aware(datetime.combine(paid_on, time(12, 0))),
        )
    return participant


# ---------- Исключение и заявки ----------


def registered_request(participant):
    return participant.requests.filter(
        status=ExclusionRequest.Status.REGISTERED
    ).first()


def _exclude(participant, reason):
    participant.status = Participant.Status.EXCLUDED
    participant.exclusion_reason = reason
    participant.save(update_fields=["status", "exclusion_reason"])
    sync_role(participant.user)


def exclude_violator(participant):
    """Forced exclusion for repeated violations of the chat rules."""
    if not participant.is_active:
        raise CourseError("Участник уже исключён из курса.", "already_excluded", 409)
    if is_archived(participant.course):
        raise CourseError("Состав участников архивного курса не изменяется.")
    with transaction.atomic():
        _exclude(participant, Participant.Reason.VIOLATION)
        created = None
        paid = participant.course.is_paid and hasattr(participant, "payment")
        if paid and registered_request(participant) is None:
            created = ExclusionRequest.objects.create(
                participant=participant, basis=ExclusionRequest.Basis.VIOLATION
            )
    return created


def refusable_participations(user):
    """Courses of the participant for the request form."""
    now = timezone.now()
    return (
        Participant.objects.filter(user=user, status=Participant.Status.ACTIVE)
        .exclude(course__state=Course.State.ARCHIVED)
        .exclude(course__end_at__lte=now)
        .exclude(requests__status=ExclusionRequest.Status.REGISTERED)
        .select_related("course", "payment")
    )


def submit_request(user, participant, reason="", policy_ack=False):
    if participant.user_id != user.pk or not participant.is_active:
        raise CourseError(
            "Подать заявку может только активный участник курса.", "forbidden", 403
        )
    if is_archived(participant.course):
        raise CourseError("По архивному курсу заявка не подаётся.", "archived", 409)
    if registered_request(participant):
        raise CourseError(
            "По этому курсу уже есть заявка на рассмотрении.", "request_exists", 409
        )
    course = participant.course
    if course.is_paid and not policy_ack:
        raise CourseError(
            "Подтвердите, что ознакомлены с политикой возврата средств.",
            "policy_required",
            field="policy_ack",
        )
    with transaction.atomic():
        try:
            req = ExclusionRequest.objects.create(
                participant=participant,
                basis=ExclusionRequest.Basis.PARTICIPANT,
                reason=(reason or "").strip(),
            )
        except IntegrityError as exc:
            raise CourseError(
                "По этому курсу уже есть заявка на рассмотрении.", "request_exists", 409
            ) from exc
        if not course.is_paid:
            # Free course: the participant is excluded at once
            _exclude(participant, Participant.Reason.REQUEST)
            req.status = ExclusionRequest.Status.DONE
            req.save(update_fields=["status"])
    return req


def passed_share(req):
    """Passed part of the course at the moment the request was submitted (0..1)."""
    course = req.participant.course
    total = (course.end_at - course.start_at).total_seconds()
    passed = (req.created_at - course.start_at).total_seconds() / total
    return max(0.0, min(1.0, passed))


def submitted_before_start(req):
    return req.created_at < req.participant.course.start_at


def can_reject(req):
    return (
        req.status == ExclusionRequest.Status.REGISTERED
        and req.participant.is_active
        and not hasattr(req, "refund")
    )


def _payment_of(req):
    payment = getattr(req.participant, "payment", None)
    if payment is None:
        raise CourseError("По заявке нет данных об оплате: возврат не требуется.")
    return payment


def refund(req, fpr):
    """«Вернуть средства» (service) or «Средства возвращены» (offline payment)."""
    if req.status != ExclusionRequest.Status.REGISTERED:
        raise CourseError("Заявка уже закрыта.", "closed", 409)
    if hasattr(req, "refund"):
        raise CourseError("Возврат по заявке уже выполнен.", "refunded", 409)
    payment = _payment_of(req)
    fpr = Decimal(fpr)
    if submitted_before_start(req) and fpr != 0:
        raise CourseError("Заявка подана до старта курса: ФПР равны нулю.", field="fpr")
    if fpr < 0 or fpr > payment.amount:
        raise CourseError(
            "ФПР должны быть не меньше нуля и не больше оплаченной суммы.", field="fpr"
        )
    amount = payment.amount - fpr
    if not payment.is_offline and amount > 0:
        try:
            get_gateway().refund(payment.transaction_id, amount)
        except GatewayError as exc:
            raise CourseError(
                f"{exc} Заявка остаётся зарегистрированной, возврат можно "
                "отправить повторно.",
                "gateway_error",
                502,
            ) from exc
    return Refund.objects.create(request=req, amount=amount, fpr=fpr)


def close_request(req):
    if req.status != ExclusionRequest.Status.REGISTERED:
        raise CourseError("Заявка уже закрыта.", "closed", 409)
    if getattr(req.participant, "payment", None) and not hasattr(req, "refund"):
        raise CourseError(
            "Закрыть заявку можно только после возврата средств.", "not_refunded", 409
        )
    with transaction.atomic():
        if req.participant.is_active:
            _exclude(req.participant, Participant.Reason.REQUEST)
        req.status = ExclusionRequest.Status.DONE
        req.save(update_fields=["status"])
    return req


def reject_request(req):
    if not can_reject(req):
        raise CourseError(
            "Заявку нельзя отклонить: участник уже исключён из курса или возврат "
            "уже выполнен.",
            "cannot_reject",
            409,
        )
    req.status = ExclusionRequest.Status.REJECTED
    req.save(update_fields=["status"])
    return req


# ---------- Для модуля управления учётными записями ----------


def get_open_obligations(user):
    """Return human-readable descriptions of the user's unfinished obligations.

    An unfinished obligation is participation in an unfinished paid course or
    an exclusion request whose refund has not been completed yet. The
    authorization module refuses to delete an account while this list is not
    empty and shows the reasons to the user.
    """
    now = timezone.now()
    reasons = []
    active = Participant.objects.filter(
        user=user,
        status=Participant.Status.ACTIVE,
        course__status=Course.Status.PAID,
        course__end_at__gt=now,
    ).select_related("course")
    for participant in active:
        reasons.append(f"Участие в платном курсе «{participant.course.name}».")
    pending = ExclusionRequest.objects.filter(
        participant__user=user,
        status=ExclusionRequest.Status.REGISTERED,
        participant__course__status=Course.Status.PAID,
    ).select_related("participant__course")
    for req in pending:
        reasons.append(
            f"Заявка на исключение из курса «{req.participant.course.name}» "
            "ещё не обработана."
        )
    return reasons
