from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from authorization.models import User
from authorization.services import anonymize_user


class Command(BaseCommand):
    help = (
        "Обезличивает персональные данные учётных записей, удалённых более "
        "DELETED_ACCOUNT_RETENTION_DAYS дней назад (152-ФЗ)."
    )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(
            days=settings.DELETED_ACCOUNT_RETENTION_DAYS
        )
        users = User.objects.filter(
            status=User.Status.DELETED, deleted_at__lt=cutoff
        ).exclude(email__endswith="@invalid")
        count = 0
        for user in users:
            anonymize_user(user)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Обезличено учётных записей: {count}"))
