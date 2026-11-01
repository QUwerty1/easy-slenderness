from django.contrib.auth import get_user_model
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import serializers as s
from . import services
from .models import Course, ExclusionRequest, Participant
from .payments import FakeGateway, GatewayError, get_gateway
from .permissions import IsAdmin, IsLearner
from .services import CourseError


def error_response(exc: CourseError):
    if exc.field:
        return Response({exc.field: [exc.message]}, status=exc.status)
    return Response({"detail": exc.message, "code": exc.code}, status=exc.status)


class CourseAPIView(APIView):
    """Turns ``CourseError`` raised by the services into an API response."""

    def handle_exception(self, exc):
        if isinstance(exc, CourseError):
            return error_response(exc)
        return super().handle_exception(exc)


def ctx(request):
    return {"request": request}


# ---------- Курсы ----------


class AvailableCoursesView(CourseAPIView):
    @extend_schema(
        summary="Получить список курсов (открытых для записи)",
        responses=s.CourseSerializer(many=True),
    )
    def get(self, request):
        courses = services.available_courses()
        return Response(
            s.CourseSerializer(courses, many=True, context=ctx(request)).data
        )


class MyCoursesView(CourseAPIView):
    @extend_schema(
        summary="Получить список моих курсов", responses=s.CourseSerializer(many=True)
    )
    def get(self, request):
        if services.is_admin(request.user):
            raise CourseError(
                "У администратора нет списка «Мои курсы».", "forbidden", 403
            )
        courses = services.my_courses(request.user)
        return Response(
            s.CourseSerializer(courses, many=True, context=ctx(request)).data
        )


class CourseListView(CourseAPIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Получить список всех курсов",
        parameters=[OpenApiParameter("state", enum=Course.State.values)],
        responses=s.CourseSerializer(many=True),
    )
    def get(self, request):
        courses = Course.objects.all()
        state = request.query_params.get("state")
        if state in Course.State.values:
            courses = courses.filter(state=state)
        return Response(
            s.CourseSerializer(courses, many=True, context=ctx(request)).data
        )

    @extend_schema(
        summary="Создание курса",
        request=s.CourseCreateSerializer,
        responses={201: s.CourseSerializer},
    )
    def post(self, request):
        serializer = s.CourseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = services.create_course(**serializer.validated_data)
        return Response(
            s.CourseSerializer(course, context=ctx(request)).data,
            status=status.HTTP_201_CREATED,
        )


class CourseDetailView(CourseAPIView):
    def get_course(self, request, pk):
        course = get_object_or_404(Course, pk=pk)
        if not services.can_view_card(request.user, course):
            raise CourseError("Нет доступа к курсу.", "forbidden", 403)
        return course

    @extend_schema(summary="Просмотр курса", responses=s.CourseSerializer)
    def get(self, request, pk):
        course = self.get_course(request, pk)
        return Response(s.CourseSerializer(course, context=ctx(request)).data)

    @extend_schema(
        summary="Редактирование курса",
        request=s.CourseUpdateSerializer,
        responses=s.CourseSerializer,
    )
    def patch(self, request, pk):
        if not services.is_admin(request.user):
            raise CourseError(
                "Редактировать курс может только администратор.", "forbidden", 403
            )
        course = get_object_or_404(Course, pk=pk)
        serializer = s.CourseUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_course(course, **serializer.validated_data)
        return Response(s.CourseSerializer(course, context=ctx(request)).data)


# ---------- Запись и оплата ----------


class EnrollView(CourseAPIView):
    permission_classes = [IsLearner]

    @extend_schema(
        summary="Запись на курс",
        request=s.EnrollSerializer,
        responses=s.EnrollResultSerializer,
    )
    def post(self, request, pk):
        course = get_object_or_404(Course, pk=pk)
        serializer = s.EnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            services.enroll(request.user, course, serializer.validated_data)
        )


@method_decorator(csrf_exempt, name="dispatch")
class PaymentWebhookView(CourseAPIView):
    """Notification of the payment service (YooKassa)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Уведомление платёжного сервиса",
        request={"application/json": {"type": "object"}},
        responses={200: None},
    )
    def post(self, request):
        try:
            result = get_gateway().parse_notification(request.data)
        except GatewayError as exc:
            return Response({"detail": str(exc)}, status=400)
        services.confirm_payment(result)
        return Response(status=200)


class FakePaymentView(CourseAPIView):
    """Test payment page of ``FakeGateway``: imitates the service notification."""

    @extend_schema(
        summary="Тестовая оплата (только для PAYMENT_GATEWAY = fake)",
        request=s.FakePaymentSerializer,
        responses={204: None},
    )
    def post(self, request):
        gateway = get_gateway()
        if not isinstance(gateway, FakeGateway):
            raise CourseError("Тестовая оплата отключена.", "not_found", 404)
        serializer = s.FakePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.confirm_payment(gateway.parse_notification(serializer.validated_data))
        return Response(status=status.HTTP_204_NO_CONTENT)


class EnrollmentStatusView(CourseAPIView):
    @extend_schema(
        summary="Стал ли пользователь участником курса (после оплаты)",
        responses={
            200: {
                "type": "object",
                "properties": {"is_participant": {"type": "boolean"}},
            }
        },
    )
    def get(self, request, pk):
        course = get_object_or_404(Course, pk=pk)
        participant = services.active_participant(request.user, course)
        return Response({"is_participant": participant is not None})


# ---------- Участники ----------


class ParticipantsView(CourseAPIView):
    @extend_schema(
        summary="Просмотр списка участников курса",
        parameters=[
            OpenApiParameter("full_name"),
            OpenApiParameter("phone"),
            OpenApiParameter("email"),
            OpenApiParameter("status", enum=Participant.Status.values),
        ],
        responses=s.ParticipantAdminSerializer(many=True),
    )
    def get(self, request, pk):
        course = get_object_or_404(Course, pk=pk)
        if not services.can_view_course(request.user, course):
            raise CourseError("Нет доступа к списку участников.", "forbidden", 403)
        participants = course.participants.select_related("user")
        if not services.is_admin(request.user):
            active = participants.filter(status=Participant.Status.ACTIVE)
            return Response(s.ParticipantPublicSerializer(active, many=True).data)
        q = request.query_params
        if q.get("full_name"):
            participants = participants.filter(
                user__full_name__icontains=q["full_name"]
            )
        if q.get("phone"):
            digits = "".join(ch for ch in q["phone"] if ch.isdigit())
            participants = participants.filter(user__phone__contains=digits)
        if q.get("email"):
            participants = participants.filter(user__email__icontains=q["email"])
        if q.get("status") in Participant.Status.values:
            participants = participants.filter(status=q["status"])
        return Response(s.ParticipantAdminSerializer(participants, many=True).data)


class CandidatesView(CourseAPIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Пользователи для ручного зачисления",
        parameters=[
            OpenApiParameter("full_name"),
            OpenApiParameter("phone"),
            OpenApiParameter("email"),
        ],
        responses=s.CandidateSerializer(many=True),
    )
    def get(self, request, pk):
        course = get_object_or_404(Course, pk=pk)
        q = request.query_params
        users = services.candidates(
            course, q.get("full_name", ""), q.get("phone", ""), q.get("email", "")
        )
        active = set(
            course.participants.filter(status=Participant.Status.ACTIVE).values_list(
                "user_id", flat=True
            )
        )
        data = [
            {
                "id": u.pk,
                "full_name": u.full_name,
                "phone": u.phone,
                "email": u.email,
                "is_participant": u.pk in active,
            }
            for u in users
        ]
        return Response(s.CandidateSerializer(data, many=True).data)


class ManualEnrollView(CourseAPIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Ручное зачисление на курс (оплата вне системы)",
        request=s.ManualEnrollSerializer,
        responses={201: s.ParticipantAdminSerializer},
    )
    def post(self, request, pk):
        course = get_object_or_404(Course, pk=pk)
        serializer = s.ManualEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = get_object_or_404(get_user_model(), pk=data["user_id"])
        participant = services.manual_enroll(
            course, user, data["amount"], data["paid_on"]
        )
        return Response(
            s.ParticipantAdminSerializer(participant).data,
            status=status.HTTP_201_CREATED,
        )


class ExcludeView(CourseAPIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Исключение участника курса (нарушение правил)",
        request=None,
        responses=s.ParticipantAdminSerializer,
    )
    def post(self, request, pk):
        participant = get_object_or_404(Participant, pk=pk)
        created = services.exclude_violator(participant)
        data = s.ParticipantAdminSerializer(participant).data
        data["request_created"] = created is not None
        return Response(data)


# ---------- Заявки на исключение ----------


class RefusableView(CourseAPIView):
    permission_classes = [IsLearner]

    @extend_schema(
        summary="Курсы, по которым можно подать заявку",
        responses=s.RefusableSerializer(many=True),
    )
    def get(self, request):
        items = services.refusable_participations(request.user)
        return Response(
            s.RefusableSerializer(items, many=True, context=ctx(request)).data
        )


class MyRequestsView(CourseAPIView):
    permission_classes = [IsLearner]

    @extend_schema(
        summary="Просмотр своих заявок", responses=s.MyRequestSerializer(many=True)
    )
    def get(self, request):
        # Requests created automatically for violators are not shown to the user
        requests = ExclusionRequest.objects.filter(
            participant__user=request.user, basis=ExclusionRequest.Basis.PARTICIPANT
        ).select_related("participant__course", "refund")
        return Response(s.MyRequestSerializer(requests, many=True).data)

    @extend_schema(
        summary="Подача заявки на исключение из курса",
        request=s.SubmitRequestSerializer,
        responses={201: s.MyRequestSerializer},
    )
    def post(self, request):
        serializer = s.SubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        participant = get_object_or_404(
            Participant, pk=data["participant_id"], user=request.user
        )
        req = services.submit_request(
            request.user, participant, data["reason"], data["policy_ack"]
        )
        return Response(s.MyRequestSerializer(req).data, status=status.HTTP_201_CREATED)


class RequestListView(CourseAPIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Просмотр списка заявок на исключение",
        parameters=[OpenApiParameter("status", enum=ExclusionRequest.Status.values)],
        responses=s.RequestListSerializer(many=True),
    )
    def get(self, request):
        requests = ExclusionRequest.objects.select_related(
            "participant__user", "participant__course"
        ).annotate(
            registered_first=Case(
                When(status=ExclusionRequest.Status.REGISTERED, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        state = request.query_params.get("status")
        if state in ExclusionRequest.Status.values:
            requests = requests.filter(status=state)
        requests = requests.order_by("registered_first", "-created_at")
        return Response(s.RequestListSerializer(requests, many=True).data)


class RequestDetailView(CourseAPIView):
    permission_classes = [IsAdmin]

    def get_request(self, pk):
        return get_object_or_404(
            ExclusionRequest.objects.select_related(
                "participant__user", "participant__course"
            ),
            pk=pk,
        )

    @extend_schema(
        summary="Обработка заявки на возврат средств: данные заявки",
        responses=s.RequestDetailSerializer,
    )
    def get(self, request, pk):
        req = self.get_request(pk)
        return Response(s.RequestDetailSerializer(req, context=ctx(request)).data)


class RequestRefundView(RequestDetailView):
    @extend_schema(
        summary="Вернуть средства / Средства возвращены",
        request=s.RefundRequestSerializer,
        responses=s.RequestDetailSerializer,
    )
    def post(self, request, pk):
        req = self.get_request(pk)
        serializer = s.RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.refund(req, serializer.validated_data["fpr"])
        req = self.get_request(pk)
        return Response(s.RequestDetailSerializer(req, context=ctx(request)).data)


class RequestCloseView(RequestDetailView):
    @extend_schema(
        summary="Закрыть заявку", request=None, responses=s.RequestDetailSerializer
    )
    def post(self, request, pk):
        req = self.get_request(pk)
        services.close_request(req)
        return Response(s.RequestDetailSerializer(req, context=ctx(request)).data)


class RequestRejectView(RequestDetailView):
    @extend_schema(
        summary="Отклонить заявку", request=None, responses=s.RequestDetailSerializer
    )
    def post(self, request, pk):
        req = self.get_request(pk)
        services.reject_request(req)
        return Response(s.RequestDetailSerializer(req, context=ctx(request)).data)
