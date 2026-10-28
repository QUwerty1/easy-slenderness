from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User
from .services import normalize_phone

PHONE_FORMAT_ERROR = "Введите номер в формате +7 XXX XXX-XX-XX."


def validate_phone_value(value):
    phone = normalize_phone(value)
    if phone is None:
        raise serializers.ValidationError(PHONE_FORMAT_ERROR)
    return phone


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    requires_2fa = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "role",
            "role_display",
            "totp_enabled",
            "requires_2fa",
        ]
        read_only_fields = fields


class SessionStateSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=["anon", "pre2fa", "setup2fa", "authed"])
    user = UserSerializer(allow_null=True)


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=32)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    pd_consent = serializers.BooleanField()

    def validate_full_name(self, value):
        return " ".join(value.split())

    def validate_phone(self, value):
        return validate_phone_value(value)

    def validate_email(self, value):
        return value.lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_pd_consent(self, value):
        if not value:
            raise serializers.ValidationError(
                "Необходимо согласие на обработку персональных данных."
            )
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class LoginResultSerializer(serializers.Serializer):
    next = serializers.ChoiceField(choices=["home", "2fa", "2fa_setup"])
    user = UserSerializer(required=False)


class CodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)


class ProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=32)
    email = serializers.EmailField()
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_full_name(self, value):
        return " ".join(value.split())

    def validate_phone(self, value):
        phone = validate_phone_value(value)
        user = self.context["request"].user
        if User.objects.filter(phone=phone).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("Этот телефон уже зарегистрирован.")
        return phone

    def validate_email(self, value):
        value = value.lower()
        user = self.context["request"].user
        if User.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("Этот email уже зарегистрирован.")
        return value

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Неверный пароль.")
        return value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Неверный текущий пароль.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False)

    def validate_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Неверный пароль.")
        return value


class TotpSetupSerializer(serializers.Serializer):
    secret = serializers.CharField()
    otpauth_uri = serializers.CharField()
    qr_svg = serializers.CharField()


class BackupCodesSerializer(serializers.Serializer):
    backup_codes = serializers.ListField(child=serializers.CharField())
    user = UserSerializer()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetTokenSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()


class PasswordResetConfirmSerializer(PasswordResetTokenSerializer):
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField(required=False)


class DeletionBlockedSerializer(DetailSerializer):
    reasons = serializers.ListField(child=serializers.CharField())
