import hashlib
import re
import secrets
from datetime import timedelta

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from course.services import get_open_obligations

from .models import BackupCode, User, UserSession

# Session keys for the intermediate login states (the user is not logged in yet)
PRE_AUTH_KEY = "pre_auth_user_id"
SETUP_2FA_KEY = "setup_2fa_user_id"

BACKUP_CODES_COUNT = 10
BACKUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class AccountLocked(Exception):
    pass


class AccountDeletionBlocked(Exception):
    def __init__(self, reasons):
        super().__init__(reasons)
        self.reasons = reasons


def normalize_phone(value):
    """Bring a Russian phone number to the +7XXXXXXXXXX form, or return None."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) == 10 and digits[0] == "9":
        return f"+7{digits}"
    return None


# Lockout


def is_locked(user):
    return user.locked_until is not None and user.locked_until > timezone.now()


def register_failure(user):
    """Count a failed password or 2FA code; return True if the account got locked."""
    user.failed_attempts += 1
    locked = user.failed_attempts >= settings.AUTH_LOCKOUT_ATTEMPTS
    if locked:
        user.failed_attempts = 0
        user.locked_until = timezone.now() + timedelta(
            minutes=settings.AUTH_LOCKOUT_MINUTES
        )
    user.save(update_fields=["failed_attempts", "locked_until"])
    return locked


def reset_failures(user):
    if user.failed_attempts or user.locked_until:
        user.failed_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_attempts", "locked_until"])


# Sessions


def start_session(request, user):
    """Fully log the user in, dropping any intermediate login state."""
    request.session.pop(PRE_AUTH_KEY, None)
    request.session.pop(SETUP_2FA_KEY, None)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")


def terminate_sessions(user, except_key=None):
    sessions = UserSession.objects.filter(user=user)
    if except_key:
        sessions = sessions.exclude(session_key=except_key)
    keys = list(sessions.values_list("session_key", flat=True))
    Session.objects.filter(session_key__in=keys).delete()
    sessions.delete()


def get_session_user(request, key):
    user_id = request.session.get(key)
    if user_id is None:
        return None
    return User.objects.filter(pk=user_id, status=User.Status.ACTIVE).first()


# Password login (F2)


def login_with_password(request, email, password):
    """Check the credentials and return the next step: home, 2fa or 2fa_setup.

    Returns None for invalid credentials, raises AccountLocked when the account
    is locked or gets locked by this attempt.
    """
    user = User.objects.filter(email__iexact=email.strip()).first()
    if user is None:
        # Spend the same time hashing so response time does not reveal the account
        User().set_password(password)
        return None
    if is_locked(user):
        raise AccountLocked
    if not user.check_password(password) or not user.is_active:
        if register_failure(user):
            raise AccountLocked
        return None

    reset_failures(user)
    request.session.cycle_key()
    if user.totp_enabled:
        request.session[PRE_AUTH_KEY] = user.pk
        return "2fa"
    if user.requires_2fa:
        request.session[SETUP_2FA_KEY] = user.pk
        return "2fa_setup"
    start_session(request, user)
    return "home"


# TOTP (F3, F4)


def _fernet():
    return Fernet(settings.TOTP_ENCRYPTION_KEY)


def encrypt_secret(secret):
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token):
    return _fernet().decrypt(token.encode()).decode()


def _hash_backup_code(code):
    normalized = re.sub(r"[^A-Z0-9]", "", code.upper())
    return hashlib.sha256(normalized.encode()).hexdigest()


def _generate_backup_code():
    raw = "".join(secrets.choice(BACKUP_CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def begin_totp_setup(user):
    """Issue a new pending secret and return its otpauth URI and QR code (SVG)."""
    secret = pyotp.random_base32()
    user.totp_pending_secret_encrypted = encrypt_secret(secret)
    user.save(update_fields=["totp_pending_secret_encrypted"])
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name=settings.TOTP_ISSUER
    )
    qr_svg = qrcode.make(
        uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8
    ).to_string(encoding="unicode")
    return {"secret": secret, "otpauth_uri": uri, "qr_svg": qr_svg}


def confirm_totp_setup(user, code):
    """Enable 2FA if the code matches the pending secret; return backup codes."""
    if not user.totp_pending_secret_encrypted:
        return None
    secret = decrypt_secret(user.totp_pending_secret_encrypted)
    if not pyotp.TOTP(secret).verify(code.strip(), valid_window=1):
        return None

    codes = [_generate_backup_code() for _ in range(BACKUP_CODES_COUNT)]
    with transaction.atomic():
        user.totp_secret_encrypted = user.totp_pending_secret_encrypted
        user.totp_pending_secret_encrypted = ""
        user.totp_enabled = True
        user.save(
            update_fields=[
                "totp_secret_encrypted",
                "totp_pending_secret_encrypted",
                "totp_enabled",
            ]
        )
        user.backup_codes.all().delete()
        BackupCode.objects.bulk_create(
            BackupCode(user=user, code_hash=_hash_backup_code(c)) for c in codes
        )
    return codes


def verify_second_factor(user, code):
    """Accept a current TOTP code (±1 step) or an unused backup code."""
    code = code.strip()
    if re.fullmatch(r"\d{6}", code):
        secret = decrypt_secret(user.totp_secret_encrypted)
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    used = user.backup_codes.filter(
        code_hash=_hash_backup_code(code), used_at__isnull=True
    ).update(used_at=timezone.now())
    return used > 0


def reset_totp(user):
    """Turn 2FA off; used by an administrator when backup codes are lost."""
    user.totp_enabled = False
    user.totp_secret_encrypted = ""
    user.totp_pending_secret_encrypted = ""
    user.save(
        update_fields=[
            "totp_enabled",
            "totp_secret_encrypted",
            "totp_pending_secret_encrypted",
        ]
    )
    user.backup_codes.all().delete()


# Password reset (F5)


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def request_password_reset(email):
    user = User.objects.filter(
        email__iexact=email.strip(), status=User.Status.ACTIVE
    ).first()
    if user is None:
        return
    token = secrets.token_urlsafe(32)
    # Only the latest token is kept: a new request replaces the previous one
    user.reset_token_hash = _hash_token(token)
    user.reset_token_expires_at = timezone.now() + timedelta(
        minutes=settings.PASSWORD_RESET_TTL_MINUTES
    )
    user.save(update_fields=["reset_token_hash", "reset_token_expires_at"])

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    send_mail(
        "Сброс пароля — Легкая стройность",
        "Чтобы задать новый пароль, перейдите по ссылке "
        f"(действует {settings.PASSWORD_RESET_TTL_MINUTES} минут):\n{link}\n\n"
        "Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )


def check_reset_token(uid, token):
    """Return the user the reset link belongs to, or None if the link is invalid."""
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id, status=User.Status.ACTIVE)
    except ValueError, TypeError, User.DoesNotExist:
        return None
    if (
        not user.reset_token_hash
        or user.reset_token_expires_at is None
        or user.reset_token_expires_at < timezone.now()
        or not constant_time_compare(user.reset_token_hash, _hash_token(token))
    ):
        return None
    return user


def reset_password(user, new_password):
    user.set_password(new_password)
    user.reset_token_hash = ""
    user.reset_token_expires_at = None
    user.failed_attempts = 0
    user.locked_until = None
    user.save()
    terminate_sessions(user)


# Password change (F6)


def change_password(request, new_password):
    user = request.user
    old_key = request.session.session_key
    user.set_password(new_password)
    user.save(update_fields=["password"])
    # Keeps the current session valid; it also rotates the session key
    update_session_auth_hash(request, user)
    new_key = request.session.session_key
    UserSession.objects.filter(session_key=old_key).update(session_key=new_key)
    terminate_sessions(user, except_key=new_key)


# Account deletion (F8)


def delete_account(request):
    user = request.user
    reasons = get_open_obligations(user)
    if reasons:
        raise AccountDeletionBlocked(reasons)
    user.status = User.Status.DELETED
    user.deleted_at = timezone.now()
    user.save(update_fields=["status", "deleted_at"])
    logout(request)
    terminate_sessions(user)


def anonymize_user(user):
    """Remove personal data of a deleted account (152-FZ)."""
    user.full_name = "Удалён"
    user.email = f"deleted-{user.pk}@invalid"
    user.phone = None
    user.set_unusable_password()
    user.totp_secret_encrypted = ""
    user.totp_pending_secret_encrypted = ""
    user.totp_enabled = False
    user.reset_token_hash = ""
    user.reset_token_expires_at = None
    user.save()
    user.backup_codes.all().delete()
