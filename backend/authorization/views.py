from django.contrib.auth import logout
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import User
from .permissions import IsAuthOrSetup2FA, IsGuest, IsPreAuth
from .serializers import (
    BackupCodesSerializer,
    CodeSerializer,
    DeletionBlockedSerializer,
    DetailSerializer,
    LoginResultSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetTokenSerializer,
    PasswordSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    SessionStateSerializer,
    TotpSetupSerializer,
    UserSerializer,
)

INVALID_CREDENTIALS = "Неверный email или пароль."
INVALID_CODE = "Неверный код подтверждения."
LOCKED = "Слишком много неудачных попыток. Вход заблокирован на 15 минут."
ALREADY_REGISTERED = "Учётная запись с таким email или телефоном уже зарегистрирована."
RESET_SENT = (
    "Если учётная запись существует, на указанный адрес отправлена ссылка "
    "для сброса пароля."
)
INVALID_RESET_LINK = "Ссылка для сброса пароля недействительна или устарела."


def detail(message, code, status_code):
    return Response({"detail": message, "code": code}, status=status_code)


@method_decorator(csrf_protect, name="dispatch")
class AuthAPIView(APIView):
    """Base view enforcing CSRF also for anonymous requests (login CSRF)."""


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SessionView(AuthAPIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="Текущее состояние сессии", responses=SessionStateSerializer)
    def get(self, request):
        user = None
        if request.user.is_authenticated:
            stage, user = "authed", request.user
        elif services.PRE_AUTH_KEY in request.session:
            stage = "pre2fa"
        elif services.SETUP_2FA_KEY in request.session:
            stage = "setup2fa"
            user = services.get_session_user(request, services.SETUP_2FA_KEY)
        else:
            stage = "anon"
        data = {"stage": stage, "user": UserSerializer(user).data if user else None}
        return Response(data)


class RegisterView(AuthAPIView):
    permission_classes = [IsGuest]
    throttle_scope = "register"

    @extend_schema(
        summary="Регистрация (F1)",
        request=RegisterSerializer,
        responses={201: UserSerializer, 409: DetailSerializer},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if User.objects.filter(
            Q(email__iexact=data["email"]) | Q(phone=data["phone"])
        ).exists():
            return detail(ALREADY_REGISTERED, "already_registered", 409)
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=data["email"],
                    password=data["password"],
                    full_name=data["full_name"],
                    phone=data["phone"],
                    pd_consent_at=timezone.now(),
                )
        except IntegrityError:
            return detail(ALREADY_REGISTERED, "already_registered", 409)
        services.start_session(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(AuthAPIView):
    permission_classes = [IsGuest]
    throttle_scope = "login"

    @extend_schema(
        summary="Вход по email и паролю (F2)",
        request=LoginSerializer,
        responses={
            200: LoginResultSerializer,
            400: DetailSerializer,
            423: DetailSerializer,
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return detail(INVALID_CREDENTIALS, "invalid_credentials", 400)
        try:
            next_step = services.login_with_password(
                request,
                serializer.validated_data["email"],
                serializer.validated_data["password"],
            )
        except services.AccountLocked:
            return detail(LOCKED, "locked", 423)
        if next_step is None:
            return detail(INVALID_CREDENTIALS, "invalid_credentials", 400)
        data = {"next": next_step}
        if next_step == "home":
            data["user"] = UserSerializer(request.user).data
        return Response(data)


class LoginTwoFactorView(AuthAPIView):
    permission_classes = [IsPreAuth]
    throttle_scope = "2fa"

    @extend_schema(
        summary="Подтверждение входа кодом 2FA или резервным кодом (F4)",
        request=CodeSerializer,
        responses={200: UserSerializer, 400: DetailSerializer, 423: DetailSerializer},
    )
    def post(self, request):
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.get_session_user(request, services.PRE_AUTH_KEY)
        if user is None or services.is_locked(user):
            request.session.flush()
            return detail(LOCKED, "locked", 423)
        if not services.verify_second_factor(user, serializer.validated_data["code"]):
            if services.register_failure(user):
                request.session.flush()
                return detail(LOCKED, "locked", 423)
            return detail(INVALID_CODE, "invalid_code", 400)
        services.reset_failures(user)
        services.start_session(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(AuthAPIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Выход и отмена незавершённого входа",
        request=None,
        responses={204: None},
    )
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(AuthAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Текущий пользователь", responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(
        summary="Изменение личных данных (F7)",
        request=ProfileUpdateSerializer,
        responses=UserSerializer,
    )
    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = request.user
        for field in ("full_name", "phone", "email"):
            setattr(user, field, serializer.validated_data[field])
        try:
            user.save(update_fields=["full_name", "phone", "email"])
        except IntegrityError:
            return detail(ALREADY_REGISTERED, "already_registered", 409)
        return Response(UserSerializer(user).data)


class PasswordChangeView(AuthAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Изменение пароля (F6)",
        request=PasswordChangeSerializer,
        responses={204: None},
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        services.change_password(request, serializer.validated_data["new_password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountDeleteView(AuthAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Удаление учётной записи (F8)",
        request=PasswordSerializer,
        responses={204: None, 409: DeletionBlockedSerializer},
    )
    def post(self, request):
        serializer = PasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            services.delete_account(request)
        except services.AccountDeletionBlocked as e:
            return Response(
                {
                    "detail": "Учётную запись нельзя удалить: есть незавершённые обязательства.",
                    "code": "obligations",
                    "reasons": e.reasons,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TwoFactorSetupMixin:
    permission_classes = [IsAuthOrSetup2FA]

    def get_acting_user(self, request):
        if request.user.is_authenticated:
            return request.user
        return services.get_session_user(request, services.SETUP_2FA_KEY)


class TwoFactorSetupView(TwoFactorSetupMixin, AuthAPIView):
    @extend_schema(
        summary="Начало включения 2FA: секрет и QR-код (F3)",
        request=None,
        responses={200: TotpSetupSerializer, 400: DetailSerializer},
    )
    def post(self, request):
        user = self.get_acting_user(request)
        if user is None:
            return detail("Сессия истекла. Войдите снова.", "session_expired", 403)
        if user.totp_enabled:
            return detail(
                "Двухфакторная аутентификация уже включена.", "already_enabled", 400
            )
        return Response(services.begin_totp_setup(user))


class TwoFactorConfirmView(TwoFactorSetupMixin, AuthAPIView):
    throttle_scope = "2fa"

    @extend_schema(
        summary="Подтверждение привязки 2FA кодом из приложения (F3)",
        request=CodeSerializer,
        responses={200: BackupCodesSerializer, 400: DetailSerializer},
    )
    def post(self, request):
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.get_acting_user(request)
        if user is None:
            return detail("Сессия истекла. Войдите снова.", "session_expired", 403)
        if user.totp_enabled:
            return detail(
                "Двухфакторная аутентификация уже включена.", "already_enabled", 400
            )
        codes = services.confirm_totp_setup(user, serializer.validated_data["code"])
        if codes is None:
            return detail(INVALID_CODE, "invalid_code", 400)
        if not request.user.is_authenticated:
            services.start_session(request, user)
        return Response({"backup_codes": codes, "user": UserSerializer(user).data})


class PasswordResetView(AuthAPIView):
    permission_classes = [IsGuest]
    throttle_scope = "password_reset"

    @extend_schema(
        summary="Запрос ссылки для сброса пароля (F5)",
        request=PasswordResetRequestSerializer,
        responses=DetailSerializer,
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(serializer.validated_data["email"])
        return Response({"detail": RESET_SENT})


class PasswordResetValidateView(AuthAPIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(
        summary="Проверка ссылки сброса пароля",
        request=PasswordResetTokenSerializer,
        responses={204: None, 400: DetailSerializer},
    )
    def post(self, request):
        serializer = PasswordResetTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if services.check_reset_token(**serializer.validated_data) is None:
            return detail(INVALID_RESET_LINK, "invalid_link", 400)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetConfirmView(AuthAPIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(
        summary="Установка нового пароля по ссылке (F5)",
        request=PasswordResetConfirmSerializer,
        responses={204: None, 400: DetailSerializer},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = services.check_reset_token(data["uid"], data["token"])
        if user is None:
            return detail(INVALID_RESET_LINK, "invalid_link", 400)
        services.reset_password(user, data["new_password"])
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
