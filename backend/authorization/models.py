from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("pd_consent_at", timezone.now())
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        USER = "user", "Пользователь"
        PARTICIPANT = "participant", "Участник курса"
        TUTOR = "tutor", "Тьютор"
        ADMIN = "admin", "Администратор"

    class Status(models.TextChoices):
        ACTIVE = "active", "Активна"
        BLOCKED = "blocked", "Заблокирована"
        DELETED = "deleted", "Удалена"

    full_name = models.CharField("ФИО", max_length=255)
    email = models.EmailField("Email", unique=True)
    # NULL after anonymization, so several deleted accounts do not clash on unique
    phone = models.CharField(  # noqa: DJ001
        "Телефон", max_length=16, unique=True, null=True
    )
    role = models.CharField(
        "Роль", max_length=16, choices=Role.choices, default=Role.USER
    )
    pd_consent_at = models.DateTimeField("Дата согласия на обработку ПДн")
    status = models.CharField(
        "Статус", max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    is_staff = models.BooleanField("Доступ к админке", default=False)
    date_joined = models.DateTimeField("Дата регистрации", default=timezone.now)
    deleted_at = models.DateTimeField("Дата удаления", null=True, blank=True)

    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    totp_enabled = models.BooleanField("2FA включена", default=False)
    totp_secret_encrypted = models.TextField(blank=True)
    # Issued during setup but not yet confirmed: does not enable 2FA
    totp_pending_secret_encrypted = models.TextField(blank=True)

    reset_token_hash = models.CharField(max_length=64, blank=True)
    reset_token_expires_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name", "phone"]

    class Meta:
        verbose_name = "учётная запись"
        verbose_name_plural = "учётные записи"

    def __str__(self):
        return self.email

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def requires_2fa(self):
        return self.role in (self.Role.TUTOR, self.Role.ADMIN)


class BackupCode(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="backup_codes"
    )
    code_hash = models.CharField(max_length=128)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "резервный код"
        verbose_name_plural = "резервные коды"

    def __str__(self):
        return f"{self.user} #{self.pk}"


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    session_key = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField("Время входа", auto_now_add=True)
    last_activity_at = models.DateTimeField(
        "Последняя активность", default=timezone.now
    )
    user_agent = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "сессия"
        verbose_name_plural = "сессии"

    def __str__(self):
        return f"{self.user} @ {self.created_at:%Y-%m-%d %H:%M}"
