from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.utils import timezone

from . import services
from .models import User, UserSession


class UserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name", "phone", "role")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.phone = services.normalize_phone(user.phone) or user.phone
        # Accounts created by an administrator: consent is collected offline
        user.pd_consent_at = timezone.now()
        if commit:
            user.save()
        return user


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class UserSessionInline(admin.TabularInline):
    model = UserSession
    extra = 0
    readonly_fields = ("created_at", "last_activity_at", "user_agent", "ip")
    exclude = ("session_key",)
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm
    ordering = ("email",)
    list_display = ("email", "full_name", "phone", "role", "status", "totp_enabled")
    list_filter = ("role", "status", "totp_enabled")
    search_fields = ("email", "full_name", "phone")
    readonly_fields = (
        "pd_consent_at",
        "date_joined",
        "deleted_at",
        "last_login",
        "totp_enabled",
        "failed_attempts",
        "locked_until",
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Личные данные", {"fields": ("full_name", "phone", "pd_consent_at")}),
        ("Доступ", {"fields": ("role", "status", "is_staff", "is_superuser")}),
        (
            "Безопасность",
            {"fields": ("totp_enabled", "failed_attempts", "locked_until")},
        ),
        ("Даты", {"fields": ("date_joined", "last_login", "deleted_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "phone",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    filter_horizontal = ()
    inlines = [UserSessionInline]
    actions = ["reset_2fa", "unlock"]

    @admin.action(description="Сбросить 2FA (утрачены резервные коды)")
    def reset_2fa(self, request, queryset):
        for user in queryset:
            services.reset_totp(user)
        self.message_user(request, "2FA сброшена.", messages.SUCCESS)

    @admin.action(description="Снять блокировку входа")
    def unlock(self, request, queryset):
        queryset.update(failed_attempts=0, locked_until=None)
        self.message_user(request, "Блокировка снята.", messages.SUCCESS)
