from rest_framework import serializers

from . import services
from .models import Course, ExclusionRequest, Participant, Payment, Refund


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField(required=False)


class CourseSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    state_display = serializers.CharField(source="get_state_display", read_only=True)
    is_participant = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = (
            "id",
            "name",
            "status",
            "status_display",
            "price",
            "start_at",
            "end_at",
            "state",
            "state_display",
            "is_participant",
            "can_edit",
        )

    def get_is_participant(self, course) -> bool:
        user = self.context["request"].user
        return services.active_participant(user, course) is not None

    def get_can_edit(self, course) -> bool:
        return services.is_admin(self.context["request"].user) and services.can_edit(
            course
        )


class CourseCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=Course.Status.choices)
    start_at = serializers.DateTimeField()
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )


class CourseUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    start_at = serializers.DateTimeField(required=False)
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )


class EnrollSerializer(serializers.Serializer):
    offer = serializers.BooleanField(default=False)
    refund_policy = serializers.BooleanField(default=False)
    pd = serializers.BooleanField(default=False)


class EnrollResultSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=["enrolled", "payment"])
    participant_id = serializers.IntegerField(required=False)
    payment_url = serializers.CharField(required=False)


class FakePaymentSerializer(serializers.Serializer):
    order_id = serializers.CharField()
    success = serializers.BooleanField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class PaymentSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source="get_method_display", read_only=True)

    class Meta:
        model = Payment
        fields = ("method", "method_display", "amount", "paid_at", "transaction_id")


class ParticipantPublicSerializer(serializers.ModelSerializer):
    """For participants and tutors: no contacts (152-FZ)."""

    full_name = serializers.CharField(source="user.full_name")
    role = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = ("id", "full_name", "role")

    def get_role(self, participant) -> str:
        return "Участник курса"


class ParticipantAdminSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id")
    full_name = serializers.CharField(source="user.full_name")
    phone = serializers.CharField(source="user.phone")
    email = serializers.CharField(source="user.email")
    method_display = serializers.CharField(source="get_method_display")
    status_display = serializers.CharField(source="get_status_display")
    exclusion_reason_display = serializers.CharField(
        source="get_exclusion_reason_display"
    )
    has_registered_request = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = (
            "id",
            "user_id",
            "full_name",
            "phone",
            "email",
            "enrolled_at",
            "method",
            "method_display",
            "status",
            "status_display",
            "exclusion_reason",
            "exclusion_reason_display",
            "has_registered_request",
        )

    def get_has_registered_request(self, participant) -> bool:
        return services.registered_request(participant) is not None


class CandidateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.CharField()
    is_participant = serializers.BooleanField()


class ManualEnrollSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    paid_on = serializers.DateField()


class RefusableSerializer(serializers.ModelSerializer):
    course = CourseSerializer()
    paid_amount = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = ("id", "course", "paid_amount")

    def get_paid_amount(self, participant) -> str | None:
        payment = getattr(participant, "payment", None)
        return str(payment.amount) if payment else None


class SubmitRequestSerializer(serializers.Serializer):
    participant_id = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    policy_ack = serializers.BooleanField(default=False)


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ("amount", "fpr", "refunded_at")


class MyRequestSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="participant.course.name")
    status_display = serializers.CharField(source="get_status_display")
    refund_amount = serializers.SerializerMethodField()

    class Meta:
        model = ExclusionRequest
        fields = (
            "id",
            "course_name",
            "created_at",
            "status",
            "status_display",
            "refund_amount",
        )

    def get_refund_amount(self, req) -> str | None:
        refund = getattr(req, "refund", None)
        return str(refund.amount) if refund else None


class RequestListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="participant.user.full_name")
    course_name = serializers.CharField(source="participant.course.name")
    basis_display = serializers.CharField(source="get_basis_display")
    status_display = serializers.CharField(source="get_status_display")

    class Meta:
        model = ExclusionRequest
        fields = (
            "id",
            "full_name",
            "course_name",
            "basis",
            "basis_display",
            "created_at",
            "status",
            "status_display",
        )


class RequestDetailSerializer(RequestListSerializer):
    phone = serializers.CharField(source="participant.user.phone")
    email = serializers.CharField(source="participant.user.email")
    course = CourseSerializer(source="participant.course")
    participant_active = serializers.BooleanField(source="participant.is_active")
    passed_percent = serializers.SerializerMethodField()
    before_start = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    refund = serializers.SerializerMethodField()
    can_reject = serializers.SerializerMethodField()

    class Meta(RequestListSerializer.Meta):
        fields = (
            *RequestListSerializer.Meta.fields,
            "reason",
            "phone",
            "email",
            "course",
            "participant_active",
            "passed_percent",
            "before_start",
            "payment",
            "refund",
            "can_reject",
        )

    def get_passed_percent(self, req) -> int:
        return round(services.passed_share(req) * 100)

    def get_before_start(self, req) -> bool:
        return services.submitted_before_start(req)

    def get_payment(self, req) -> dict | None:
        payment = getattr(req.participant, "payment", None)
        return PaymentSerializer(payment).data if payment else None

    def get_refund(self, req) -> dict | None:
        refund = getattr(req, "refund", None)
        return RefundSerializer(refund).data if refund else None

    def get_can_reject(self, req) -> bool:
        return services.can_reject(req)


class RefundRequestSerializer(serializers.Serializer):
    fpr = serializers.DecimalField(max_digits=10, decimal_places=2)
