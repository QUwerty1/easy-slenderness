from django.core.management.base import BaseCommand

from homework.services import sync_expired_reports


class Command(BaseCommand):
    help = "Переводит отчеты за прошедшие дни в статус «Проверяется»."

    def handle(self, *args, **options):
        updated = sync_expired_reports()
        self.stdout.write(
            self.style.SUCCESS(f"На проверку отправлено отчетов: {updated}")
        )
