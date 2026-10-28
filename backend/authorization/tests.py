import re
from datetime import timedelta
from unittest import mock

import pyotp
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from . import services
from .models import User, UserSession

PASSWORD = "secret-pass-1"


def make_user(email="user@example.com", phone="+79001234567", **extra):
    extra.setdefault("full_name", "Иванов Иван Иванович")
    extra.setdefault("pd_consent_at", timezone.now())
    return User.objects.create_user(
        email=email, password=PASSWORD, phone=phone, **extra
    )


def enable_totp(user):
    secret = services.begin_totp_setup(user)["secret"]
    codes = services.confirm_totp_setup(user, pyotp.TOTP(secret).now())
    user.refresh_from_db()
    return secret, codes


class AuthTestCase(APITestCase):
    def setUp(self):
        cache.clear()

    def login(self, client=None, email="user@example.com", password=PASSWORD):
        client = client or self.client
        return client.post(
            reverse("authorization:login"), {"email": email, "password": password}
        )

    def stage(self, client=None):
        client = client or self.client
        return client.get(reverse("authorization:session")).data["stage"]


class RegisterTests(AuthTestCase):
    url = reverse("authorization:register")
    payload = {
        "full_name": "Петрова  Анна Сергеевна",
        "phone": "8 (900) 111-22-33",
        "email": "Anna@Example.com",
        "password": PASSWORD,
        "pd_consent": True,
    }

    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get()
        self.assertEqual(user.email, "anna@example.com")
        self.assertEqual(user.phone, "+79001112233")
        self.assertEqual(user.full_name, "Петрова Анна Сергеевна")
        self.assertEqual(user.role, User.Role.USER)
        self.assertIsNotNone(user.pd_consent_at)
        self.assertEqual(self.stage(), "authed")
        self.assertEqual(UserSession.objects.filter(user=user).count(), 1)

    def test_validation(self):
        payload = {**self.payload, "password": "short", "pd_consent": False}
        payload["phone"] = "123"
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"password", "pd_consent", "phone"})

    def test_duplicate_email_or_phone(self):
        make_user(email="anna@example.com", phone="+79990000000")
        make_user(email="other@example.com", phone="+79001112233")
        for payload in (
            self.payload,
            {**self.payload, "email": "new@example.com"},
        ):
            response = self.client.post(self.url, payload)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data["code"], "already_registered")


class LoginTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()

    def test_success(self):
        response = self.login()
        self.assertEqual(response.data["next"], "home")
        self.assertEqual(self.stage(), "authed")

    def test_same_message_for_unknown_email_and_wrong_password(self):
        wrong_password = self.login(password="wrong-password")
        unknown_email = self.login(email="nobody@example.com")
        self.assertEqual(wrong_password.status_code, 400)
        self.assertEqual(wrong_password.data, unknown_email.data)

    def test_lockout_after_five_failures(self):
        for _ in range(4):
            self.assertEqual(self.login(password="wrong").status_code, 400)
        self.assertEqual(self.login(password="wrong").status_code, 423)
        self.assertEqual(self.login().status_code, 423)

        later = timezone.now() + timedelta(minutes=16)
        with mock.patch("django.utils.timezone.now", return_value=later):
            self.assertEqual(self.login().data["next"], "home")

    def test_deleted_account_cannot_log_in(self):
        self.user.status = User.Status.DELETED
        self.user.save()
        self.assertEqual(self.login().status_code, 400)

    def test_tutor_without_2fa_goes_to_setup(self):
        self.user.role = User.Role.TUTOR
        self.user.save()
        self.assertEqual(self.login().data["next"], "2fa_setup")
        self.assertEqual(self.stage(), "setup2fa")
        # Not logged in until 2FA is enabled
        me = self.client.get(reverse("authorization:me"))
        self.assertEqual(me.status_code, 403)

        setup = self.client.post(reverse("authorization:2fa-setup"))
        code = pyotp.TOTP(setup.data["secret"]).now()
        confirm = self.client.post(reverse("authorization:2fa-confirm"), {"code": code})
        self.assertEqual(confirm.status_code, 200)
        self.assertEqual(len(confirm.data["backup_codes"]), 10)
        self.assertEqual(self.stage(), "authed")

    def test_logout(self):
        self.login()
        self.client.post(reverse("authorization:logout"))
        self.assertEqual(self.stage(), "anon")
        self.assertFalse(UserSession.objects.exists())


class TwoFactorTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()

    def test_unconfirmed_secret_does_not_enable_2fa(self):
        self.login()
        self.client.post(reverse("authorization:2fa-setup"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.totp_enabled)
        wrong = self.client.post(
            reverse("authorization:2fa-confirm"), {"code": "000000"}
        )
        self.assertEqual(wrong.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.totp_enabled)

    def test_secrets_are_stored_protected(self):
        secret, codes = enable_totp(self.user)
        self.assertNotIn(secret, self.user.totp_secret_encrypted)
        self.assertEqual(
            services.decrypt_secret(self.user.totp_secret_encrypted), secret
        )
        stored = set(self.user.backup_codes.values_list("code_hash", flat=True))
        self.assertTrue(stored.isdisjoint(codes))

    def test_login_requires_code(self):
        secret, _ = enable_totp(self.user)
        self.assertEqual(self.login().data["next"], "2fa")
        self.assertEqual(self.stage(), "pre2fa")
        response = self.client.post(
            reverse("authorization:login-2fa"), {"code": pyotp.TOTP(secret).now()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.stage(), "authed")

    def test_time_window(self):
        secret, _ = enable_totp(self.user)
        totp = pyotp.TOTP(secret)
        now = timezone.now()
        self.assertTrue(
            services.verify_second_factor(
                self.user, totp.at(now - timedelta(seconds=30))
            )
        )
        self.assertFalse(
            services.verify_second_factor(
                self.user, totp.at(now - timedelta(seconds=90))
            )
        )

    def test_backup_code_is_single_use(self):
        _, codes = enable_totp(self.user)
        self.assertTrue(services.verify_second_factor(self.user, codes[0].lower()))
        self.assertFalse(services.verify_second_factor(self.user, codes[0]))

    def test_lockout_after_five_wrong_codes(self):
        enable_totp(self.user)
        self.login()
        url = reverse("authorization:login-2fa")
        for _ in range(4):
            self.assertEqual(self.client.post(url, {"code": "000000"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"code": "000000"}).status_code, 423)
        self.assertEqual(self.stage(), "anon")
        self.assertEqual(self.login().status_code, 423)


class PasswordResetTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()

    def request_link(self, email="user@example.com"):
        return self.client.post(
            reverse("authorization:password-reset"), {"email": email}
        )

    def link_params(self):
        uid, token = re.search(r"uid=(\S+)&token=(\S+)", mail.outbox[-1].body).groups()
        return {"uid": uid, "token": token}

    def test_same_response_for_unknown_email(self):
        known = self.request_link()
        unknown = self.request_link("nobody@example.com")
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_flow(self):
        other = APIClient()
        self.login(other)
        self.request_link()
        params = self.link_params()
        validate = reverse("authorization:password-reset-validate")
        confirm = reverse("authorization:password-reset-confirm")
        self.assertEqual(self.client.post(validate, params).status_code, 204)
        response = self.client.post(
            confirm, {**params, "new_password": "brand-new-pass"}
        )
        self.assertEqual(response.status_code, 204)

        self.assertEqual(self.client.post(validate, params).status_code, 400)
        self.assertEqual(self.stage(other), "anon")
        self.assertEqual(self.login(password="brand-new-pass").data["next"], "home")

    def test_new_request_replaces_previous_token(self):
        self.request_link()
        first = self.link_params()
        self.request_link()
        validate = reverse("authorization:password-reset-validate")
        self.assertEqual(self.client.post(validate, first).status_code, 400)
        self.assertEqual(
            self.client.post(validate, self.link_params()).status_code, 204
        )

    def test_link_expires(self):
        self.request_link()
        params = self.link_params()
        later = timezone.now() + timedelta(minutes=31)
        with mock.patch("django.utils.timezone.now", return_value=later):
            response = self.client.post(
                reverse("authorization:password-reset-validate"), params
            )
        self.assertEqual(response.status_code, 400)

    def test_2fa_still_required_after_reset(self):
        enable_totp(self.user)
        self.request_link()
        self.client.post(
            reverse("authorization:password-reset-confirm"),
            {**self.link_params(), "new_password": "brand-new-pass"},
        )
        self.assertEqual(self.login(password="brand-new-pass").data["next"], "2fa")


class AccountTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.login()

    def test_change_password_keeps_current_session_only(self):
        other = APIClient()
        self.login(other)
        url = reverse("authorization:password-change")
        wrong = self.client.post(
            url, {"current_password": "wrong", "new_password": "brand-new-pass"}
        )
        self.assertEqual(wrong.status_code, 400)
        self.assertIn("current_password", wrong.data)

        response = self.client.post(
            url, {"current_password": PASSWORD, "new_password": "brand-new-pass"}
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.stage(), "authed")
        self.assertEqual(self.stage(other), "anon")
        self.assertEqual(UserSession.objects.count(), 1)

    def test_update_profile(self):
        make_user(email="taken@example.com", phone="+79995554433")
        url = reverse("authorization:me")
        data = {
            "full_name": "Иванов Пётр",
            "phone": "+7 999 555-44-33",
            "email": "new@example.com",
            "current_password": PASSWORD,
        }
        duplicate = self.client.patch(url, data)
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("phone", duplicate.data)

        wrong_password = self.client.patch(
            url, {**data, "phone": "+79001110000", "current_password": "wrong"}
        )
        self.assertEqual(wrong_password.status_code, 400)

        response = self.client.patch(url, {**data, "phone": "+79001110000"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")
        self.assertEqual(self.user.phone, "+79001110000")

    def test_delete_blocked_by_obligations(self):
        with mock.patch(
            "authorization.services.get_open_obligations",
            return_value=["Курс «Весна» не завершён"],
        ):
            response = self.client.post(
                reverse("authorization:account-delete"), {"password": PASSWORD}
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["reasons"], ["Курс «Весна» не завершён"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.status, User.Status.ACTIVE)

    def test_delete_account(self):
        other = APIClient()
        self.login(other)
        response = self.client.post(
            reverse("authorization:account-delete"), {"password": PASSWORD}
        )
        self.assertEqual(response.status_code, 204)
        self.user.refresh_from_db()
        self.assertEqual(self.user.status, User.Status.DELETED)
        self.assertEqual(self.stage(), "anon")
        self.assertEqual(self.stage(other), "anon")
        self.assertEqual(self.login().status_code, 400)

    def test_anonymize_deleted_users(self):
        from django.core.management import call_command

        self.user.status = User.Status.DELETED
        self.user.deleted_at = timezone.now() - timedelta(days=31)
        self.user.save()
        call_command("anonymize_deleted_users", stdout=mock.Mock())
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Удалён")
        self.assertIsNone(self.user.phone)
        self.assertTrue(self.user.email.endswith("@invalid"))
