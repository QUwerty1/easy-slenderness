import io
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from authorization.models import User
from course.models import Course, Participant

from .models import HomeworkReport, MealEntry, MealPhoto
from .serializers import MealCreateSerializer
from .services import participant_report_list


class HomeworkReportTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.user = User.objects.create_user(
            email="participant@example.test",
            password="test-password",
            full_name="Тестовый участник",
            phone="+79990000001",
            pd_consent_at=now,
            role=User.Role.PARTICIPANT,
        )
        start = now - timedelta(days=2)
        self.course = Course.objects.create(
            name="Тестовый курс",
            status=Course.Status.FREE,
            price=None,
            start_at=start,
            end_at=start + timedelta(days=7),
            state=Course.State.RUNNING,
        )
        self.participant = Participant.objects.create(
            user=self.user,
            course=self.course,
            method=Participant.Method.SELF,
            status=Participant.Status.ACTIVE,
        )

    def test_report_list_contains_course_days_without_creating_rows(self):
        days = participant_report_list(self.participant, self.course)
        self.assertEqual(len(days), 7)
        self.assertEqual(
            HomeworkReport.objects.filter(participant=self.participant).count(), 0
        )
        today = timezone.localdate()
        today_item = next(item for item in days if item["date"] == today)
        self.assertTrue(today_item["available"])
        self.assertFalse(today_item["is_created"])

    def test_only_one_report_per_participant_and_date(self):
        report_date = timezone.localdate()
        HomeworkReport.objects.create(
            participant=self.participant, report_date=report_date
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            HomeworkReport.objects.create(
                participant=self.participant, report_date=report_date
            )


def make_image(image_format="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, format=image_format)
    return buffer.getvalue()


class MealPhotoSecurityTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        settings_override = override_settings(MEDIA_ROOT=self.media_root)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        now = timezone.now()
        self.user = User.objects.create_user(
            email="photo@example.test",
            password="test-password",
            full_name="Участник с фото",
            phone="+79990000002",
            pd_consent_at=now,
            role=User.Role.PARTICIPANT,
        )
        start = now - timedelta(days=1)
        course = Course.objects.create(
            name="Курс с фото",
            status=Course.Status.FREE,
            price=None,
            start_at=start,
            end_at=start + timedelta(days=7),
            state=Course.State.RUNNING,
        )
        participant = Participant.objects.create(
            user=self.user,
            course=course,
            method=Participant.Method.SELF,
            status=Participant.Status.ACTIVE,
        )
        report = HomeworkReport.objects.create(
            participant=participant, report_date=timezone.localdate()
        )
        self.meal = MealEntry.objects.create(
            report=report,
            water_drank=True,
            breathing_practice=True,
            feeling=MealEntry.Feeling.HUNGER,
        )

    def validate_photo(self, name, content, content_type):
        upload = SimpleUploadedFile(name, content, content_type=content_type)
        serializer = MealCreateSerializer(
            data={
                "water_drank": True,
                "breathing_practice": True,
                "feeling": MealEntry.Feeling.HUNGER,
                "photos": [upload],
            }
        )
        return serializer

    def test_rejects_html_and_svg_disguised_as_images(self):
        payloads = [
            ("x.html", b"<script>alert(1)</script>"),
            ("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'),
            ("x.png", b"<html><script>alert(1)</script></html>"),
        ]
        for name, content in payloads:
            with self.subTest(name=name):
                serializer = self.validate_photo(name, content, "image/png")
                self.assertFalse(serializer.is_valid())
                self.assertIn("photos", serializer.errors)

    def test_rejects_unsupported_image_format(self):
        serializer = self.validate_photo("x.gif", make_image("GIF"), "image/gif")
        self.assertFalse(serializer.is_valid())

    def test_accepted_photo_is_renamed_by_real_format(self):
        serializer = self.validate_photo("evil.html", make_image("JPEG"), "text/html")
        self.assertTrue(serializer.is_valid(), serializer.errors)
        photo = MealPhoto.objects.create(
            meal=self.meal, image=serializer.validated_data["photos"][0]
        )
        self.assertTrue(photo.image.name.endswith(".jpg"))
        self.assertNotIn("evil", photo.image.name)

    def test_photo_served_with_safe_headers(self):
        serializer = self.validate_photo("a.png", make_image("PNG"), "image/png")
        self.assertTrue(serializer.is_valid(), serializer.errors)
        photo = MealPhoto.objects.create(
            meal=self.meal, image=serializer.validated_data["photos"][0]
        )
        self.client.force_login(self.user)
        response = self.client.get(f"/api/homework/photos/{photo.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("sandbox", response["Content-Security-Policy"])
        self.assertTrue(response["Content-Disposition"].startswith("inline"))

    def test_legacy_non_image_file_served_as_attachment(self):
        photo = MealPhoto(meal=self.meal)
        photo.image.save("old.html", io.BytesIO(b"<script>alert(1)</script>"))
        self.assertTrue(photo.image.name.endswith(".bin"))
        self.client.force_login(self.user)
        response = self.client.get(f"/api/homework/photos/{photo.pk}/")
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
