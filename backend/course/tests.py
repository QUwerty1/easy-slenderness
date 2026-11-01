from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from authorization.models import User

from . import services
from .models import Course, ExclusionRequest, Participant, Payment
from .payments import GatewayError, PaymentResult, make_order_id

PASSWORD = "secret-pass-1"


def make_user(n, role=User.Role.USER):
    return User.objects.create_user(
        email=f"u{n}@example.com",
        password=PASSWORD,
        phone=f"+7900000{n:04d}",
        full_name=f"Пользователь {n}",
        role=role,
        pd_consent_at=timezone.now(),
    )


def make_course(status=Course.Status.PAID, days=3, price="4900", **extra):
    start = timezone.now() + timedelta(days=days)
    return Course.objects.create(
        name=extra.pop("name", "Перезагрузка питания"),
        status=status,
        price=Decimal(price) if status == Course.Status.PAID else None,
        start_at=start,
        end_at=Course.end_for(status, start),
        **extra,
    )


def pay(user, course, succeeded=True):
    return services.confirm_payment(
        PaymentResult(
            order_id=make_order_id(user.pk, course.pk),
            succeeded=succeeded,
            amount=course.price,
            transaction_id="tx-1",
        )
    )


def start_course(course, days_ago=1):
    course.start_at = timezone.now() - timedelta(days=days_ago)
    course.end_at = Course.end_for(course.status, course.start_at)
    course.save()
    services.update_states()
    course.refresh_from_db()


class CourseTestCase(APITestCase):
    def setUp(self):
        self.user = make_user(1)
        self.tutor = make_user(2, User.Role.TUTOR)
        self.admin = make_user(3, User.Role.ADMIN)

    def as_(self, user):
        self.client.force_authenticate(user)


class CourseManagementTests(CourseTestCase):
    def test_admin_creates_course_and_end_is_calculated(self):
        self.as_(self.admin)
        start = timezone.now() + timedelta(days=5)
        response = self.client.post(
            reverse("course:list"),
            {"name": "Марафон", "status": "free", "start_at": start.isoformat()},
        )
        self.assertEqual(response.status_code, 201)
        course = Course.objects.get()
        self.assertEqual(course.end_at - course.start_at, timedelta(weeks=1))
        self.assertIsNone(course.price)
        self.assertEqual(course.state, Course.State.OPEN)

    def test_create_validation(self):
        self.as_(self.admin)
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        response = self.client.post(
            reverse("course:list"),
            {"name": " ", "status": "paid", "start_at": past, "price": "0"},
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            reverse("course:list"),
            {
                "name": "Курс",
                "status": "paid",
                "start_at": (timezone.now() + timedelta(days=1)).isoformat(),
                "price": "0",
            },
        )
        self.assertIn("price", response.data)

    def test_only_admin_creates(self):
        for user in (self.user, self.tutor):
            self.as_(user)
            response = self.client.post(reverse("course:list"), {})
            self.assertEqual(response.status_code, 403)

    def test_edit_before_start_recalculates_end(self):
        course = make_course()
        self.as_(self.admin)
        start = timezone.now() + timedelta(days=10)
        response = self.client.patch(
            reverse("course:detail", args=[course.pk]),
            {"name": "Новое", "start_at": start.isoformat(), "price": "5000"},
        )
        self.assertEqual(response.status_code, 200)
        course.refresh_from_db()
        self.assertEqual(course.end_at - course.start_at, timedelta(weeks=4))
        self.assertEqual(course.price, Decimal("5000"))

    def test_edit_after_start_forbidden(self):
        course = make_course()
        start_course(course)
        self.as_(self.admin)
        response = self.client.patch(
            reverse("course:detail", args=[course.pk]), {"name": "X"}
        )
        self.assertEqual(response.status_code, 409)

    def test_timer_starts_and_archives(self):
        course = make_course(status=Course.Status.FREE)
        start_course(course, days_ago=1)
        self.assertEqual(course.state, Course.State.RUNNING)
        start_course(course, days_ago=8)
        self.assertEqual(course.state, Course.State.ARCHIVED)
        out = StringIO()
        call_command("update_course_states", stdout=out)
        self.assertIn("архивировано", out.getvalue())

    def test_lists_by_role(self):
        open_course = make_course(name="Открыт")
        running = make_course(name="Идёт")
        start_course(running)
        Participant.objects.create(
            user=self.user, course=running, method=Participant.Method.SELF
        )
        self.as_(self.user)
        available = self.client.get(reverse("course:available")).data
        self.assertEqual([c["name"] for c in available], ["Открыт"])
        mine = self.client.get(reverse("course:my")).data
        self.assertEqual([c["name"] for c in mine], ["Идёт"])
        self.as_(self.tutor)
        self.assertEqual(len(self.client.get(reverse("course:my")).data), 2)
        self.as_(self.admin)
        self.assertEqual(self.client.get(reverse("course:my")).status_code, 403)
        response = self.client.get(reverse("course:list"), {"state": "open"})
        self.assertEqual([c["id"] for c in response.data], [open_course.pk])


class EnrollmentTests(CourseTestCase):
    def test_free_enrollment(self):
        course = make_course(status=Course.Status.FREE)
        self.as_(self.user)
        response = self.client.post(reverse("course:enroll", args=[course.pk]))
        self.assertEqual(response.data["result"], "enrolled")
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.PARTICIPANT)
        response = self.client.post(reverse("course:enroll", args=[course.pk]))
        self.assertEqual(response.data["code"], "already_participant")

    def test_paid_requires_consent_and_sends_no_personal_data(self):
        course = make_course()
        self.as_(self.user)
        url = reverse("course:enroll", args=[course.pk])
        response = self.client.post(url, {"offer": True})
        self.assertEqual(response.data["code"], "consent_required")
        response = self.client.post(
            url, {"offer": True, "refund_policy": True, "pd": True}
        )
        self.assertEqual(response.data["result"], "payment")
        payment_url = response.data["payment_url"]
        self.assertIn(f"order={self.user.pk}-{course.pk}", payment_url)
        self.assertNotIn("example.com", payment_url)
        self.assertNotIn("Пользователь", payment_url)
        self.assertFalse(Participant.objects.exists())

    def test_payment_confirmation_creates_participant_and_payment(self):
        course = make_course()
        participant = pay(self.user, course)
        self.assertEqual(participant.payment.amount, course.price)
        self.assertEqual(participant.payment.method, Payment.Method.SERVICE)

    def test_failed_payment_does_not_enroll(self):
        course = make_course()
        self.assertIsNone(pay(self.user, course, succeeded=False))
        self.assertFalse(Participant.objects.exists())

    def test_duplicate_or_late_payment_is_not_saved(self):
        course = make_course()
        pay(self.user, course)
        self.assertIsNone(pay(self.user, course))
        self.assertEqual(Payment.objects.count(), 1)
        late = make_course(name="Поздно")
        start_course(late)
        self.assertIsNone(pay(self.user, late))

    def test_fake_payment_endpoint(self):
        course = make_course()
        self.as_(self.user)
        response = self.client.post(
            reverse("course:fake-payment"),
            {"order_id": make_order_id(self.user.pk, course.pk), "success": True},
        )
        self.assertEqual(response.status_code, 204)
        status_url = reverse("course:enrollment", args=[course.pk])
        self.assertTrue(self.client.get(status_url).data["is_participant"])

    def test_enrollment_closed_after_start(self):
        course = make_course(status=Course.Status.FREE)
        start_course(course)
        self.as_(self.user)
        response = self.client.post(reverse("course:enroll", args=[course.pk]))
        self.assertEqual(response.data["code"], "enrollment_closed")

    def test_tutor_cannot_enroll(self):
        course = make_course(status=Course.Status.FREE)
        self.as_(self.tutor)
        response = self.client.post(reverse("course:enroll", args=[course.pk]))
        self.assertEqual(response.status_code, 403)

    def test_reenroll_after_exclusion_creates_new_participation(self):
        course = make_course(status=Course.Status.FREE)
        participant = services._add_participant(
            self.user, course, Participant.Method.SELF
        )
        services.submit_request(self.user, participant)
        participant.refresh_from_db()
        self.assertEqual(participant.status, Participant.Status.EXCLUDED)
        services.enroll(self.user, course, {})
        self.assertEqual(course.participants.filter(user=self.user).count(), 2)


class ManualEnrollTests(CourseTestCase):
    def test_manual_enroll_saves_offline_payment(self):
        course = make_course()
        self.as_(self.admin)
        response = self.client.post(
            reverse("course:manual-enroll", args=[course.pk]),
            {
                "user_id": self.user.pk,
                "amount": "4900",
                "paid_on": timezone.localdate().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 201)
        payment = Payment.objects.get()
        self.assertEqual(payment.method, Payment.Method.OFFLINE)
        self.assertEqual(payment.participant.method, Participant.Method.MANUAL)

    def test_manual_enroll_rules(self):
        free = make_course(status=Course.Status.FREE)
        paid = make_course()
        tomorrow = timezone.localdate() + timedelta(days=1)
        with self.assertRaises(services.CourseError):
            services.manual_enroll(free, self.user, Decimal(1), timezone.localdate())
        with self.assertRaises(services.CourseError):
            services.manual_enroll(paid, self.user, Decimal(1), tomorrow)
        with self.assertRaises(services.CourseError):
            services.manual_enroll(paid, self.user, Decimal(0), timezone.localdate())
        with self.assertRaises(services.CourseError):
            services.manual_enroll(paid, self.tutor, Decimal(1), timezone.localdate())

    def test_candidates_exclude_staff_and_filter(self):
        course = make_course()
        self.as_(self.admin)
        response = self.client.get(reverse("course:candidates", args=[course.pk]))
        self.assertEqual([u["id"] for u in response.data], [self.user.pk])
        response = self.client.get(
            reverse("course:candidates", args=[course.pk]), {"phone": "0000"}
        )
        self.assertEqual(len(response.data), 1)
        response = self.client.get(
            reverse("course:candidates", args=[course.pk]), {"email": "zzz"}
        )
        self.assertEqual(response.data, [])


class ParticipantsTests(CourseTestCase):
    def test_contacts_visible_only_to_admin(self):
        course = make_course(status=Course.Status.FREE)
        services.enroll(self.user, course, {})
        url = reverse("course:participants", args=[course.pk])
        self.as_(self.user)
        self.assertNotIn("phone", self.client.get(url).data[0])
        self.as_(self.tutor)
        self.assertNotIn("email", self.client.get(url).data[0])
        self.as_(self.admin)
        self.assertEqual(self.client.get(url).data[0]["phone"], self.user.phone)
        other = make_user(4)
        self.as_(other)
        self.assertEqual(self.client.get(url).status_code, 403)


class ExclusionTests(CourseTestCase):
    def setUp(self):
        super().setUp()
        self.course = make_course()
        self.participant = pay(self.user, self.course)

    def test_violator_of_paid_course_gets_auto_request(self):
        self.as_(self.admin)
        response = self.client.post(
            reverse("course:exclude", args=[self.participant.pk])
        )
        self.assertTrue(response.data["request_created"])
        req = ExclusionRequest.objects.get()
        self.assertEqual(req.basis, ExclusionRequest.Basis.VIOLATION)
        self.participant.refresh_from_db()
        self.assertEqual(
            self.participant.exclusion_reason, Participant.Reason.VIOLATION
        )
        # Auto requests are not shown to the user
        self.as_(self.user)
        self.assertEqual(self.client.get(reverse("course:my-requests")).data, [])

    def test_violator_with_registered_request_gets_no_second_request(self):
        services.submit_request(self.user, self.participant, policy_ack=True)
        services.exclude_violator(self.participant)
        self.assertEqual(ExclusionRequest.objects.count(), 1)

    def test_paid_request_flow_refund_then_close(self):
        self.as_(self.user)
        response = self.client.post(
            reverse("course:my-requests"),
            {"participant_id": self.participant.pk, "policy_ack": True},
        )
        self.assertEqual(response.status_code, 201)
        req = ExclusionRequest.objects.get()
        self.assertEqual(req.status, ExclusionRequest.Status.REGISTERED)
        # repeated request is refused while one is registered
        response = self.client.post(
            reverse("course:my-requests"),
            {"participant_id": self.participant.pk, "policy_ack": True},
        )
        self.assertEqual(response.data["code"], "request_exists")

        self.as_(self.admin)
        close = reverse("course:request-close", args=[req.pk])
        self.assertEqual(self.client.post(close).data["code"], "not_refunded")
        refund = reverse("course:request-refund", args=[req.pk])
        # before start FPR must be zero
        self.assertIn("fpr", self.client.post(refund, {"fpr": "100"}).data)
        response = self.client.post(refund, {"fpr": "0"})
        self.assertEqual(response.data["refund"]["amount"], "4900.00")
        self.assertFalse(response.data["can_reject"])
        reject = reverse("course:request-reject", args=[req.pk])
        self.assertEqual(self.client.post(reject).data["code"], "cannot_reject")
        self.assertEqual(
            self.client.post(refund, {"fpr": "0"}).data["code"], "refunded"
        )
        response = self.client.post(close)
        self.assertEqual(response.data["status"], "done")
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.exclusion_reason, Participant.Reason.REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.USER)

    def reload(self):
        self.participant = Participant.objects.get(pk=self.participant.pk)

    def test_fpr_limits_after_start(self):
        start_course(self.course)
        self.reload()
        req = services.submit_request(self.user, self.participant, policy_ack=True)
        with self.assertRaises(services.CourseError):
            services.refund(req, Decimal("-1"))
        with self.assertRaises(services.CourseError):
            services.refund(req, Decimal("5000"))
        refund = services.refund(req, Decimal("1000"))
        self.assertEqual(refund.amount, Decimal("3900"))
        self.assertGreater(services.passed_share(req), 0)

    def test_gateway_refusal_keeps_request_registered(self):
        req = services.submit_request(self.user, self.participant, policy_ack=True)
        with mock.patch(
            "course.payments.FakeGateway.refund", side_effect=GatewayError("Отказ.")
        ):
            self.as_(self.admin)
            response = self.client.post(
                reverse("course:request-refund", args=[req.pk]), {"fpr": "0"}
            )
        self.assertEqual(response.status_code, 502)
        req.refresh_from_db()
        self.assertEqual(req.status, ExclusionRequest.Status.REGISTERED)
        self.assertFalse(hasattr(req, "refund"))

    def test_reject_keeps_participant(self):
        req = services.submit_request(self.user, self.participant, policy_ack=True)
        services.reject_request(req)
        self.participant.refresh_from_db()
        self.assertTrue(self.participant.is_active)
        # a new request can be submitted after rejection
        services.submit_request(self.user, self.participant, policy_ack=True)

    def test_cannot_reject_request_of_excluded_participant(self):
        req = services.submit_request(self.user, self.participant, policy_ack=True)
        services.exclude_violator(self.participant)
        req.refresh_from_db()
        with self.assertRaises(services.CourseError):
            services.reject_request(req)

    def test_offline_payment_refund_is_marked(self):
        other = make_user(5)
        participant = services.manual_enroll(
            self.course, other, Decimal("4000"), timezone.localdate()
        )
        req = services.submit_request(other, participant, policy_ack=True)
        with mock.patch("course.payments.FakeGateway.refund") as gateway_refund:
            services.refund(req, Decimal("0"))
        gateway_refund.assert_not_called()
        services.close_request(req)

    def test_no_request_for_archived_course(self):
        start_course(self.course, days_ago=30)
        self.reload()
        with self.assertRaises(services.CourseError):
            services.submit_request(self.user, self.participant, policy_ack=True)
        self.assertEqual(list(services.refusable_participations(self.user)), [])

    def test_free_request_is_done_at_once(self):
        free = make_course(status=Course.Status.FREE, name="Бесплатный")
        participant = services._add_participant(self.user, free, "self")
        req = services.submit_request(self.user, participant)
        self.assertEqual(req.status, ExclusionRequest.Status.DONE)

    def test_open_obligations_block_account_deletion(self):
        reasons = services.get_open_obligations(self.user)
        self.assertEqual(len(reasons), 1)
        self.assertIn("Перезагрузка питания", reasons[0])
