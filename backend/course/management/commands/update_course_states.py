from django.core.management.base import BaseCommand

from course.services import update_states


class Command(BaseCommand):
    help = (
        "Системный таймер: переводит начавшиеся курсы в состояние «идёт», "
        "оконченные — в «архивный». Запускается планировщиком раз в минуту."
    )

    def handle(self, *args, **options):
        started, archived = update_states()
        self.stdout.write(
            self.style.SUCCESS(f"Начато курсов: {started}, архивировано: {archived}")
        )
