import os
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from authorization.models import User

PASSWORD_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# (surname, first name, patronymic); female and male forms are kept consistent
NAMES = [
    ("Иванов", "Алексей", "Петрович"),
    ("Смирнова", "Мария", "Андреевна"),
    ("Кузнецов", "Дмитрий", "Сергеевич"),
    ("Попова", "Анна", "Игоревна"),
    ("Соколов", "Михаил", "Олегович"),
    ("Лебедева", "Екатерина", "Викторовна"),
    ("Новиков", "Артём", "Николаевич"),
    ("Морозова", "Ольга", "Дмитриевна"),
    ("Волков", "Илья", "Александрович"),
    ("Козлова", "Наталья", "Евгеньевна"),
    ("Павлов", "Сергей", "Михайлович"),
    ("Семёнова", "Татьяна", "Алексеевна"),
]


def generate_password(length=12):
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


class Command(BaseCommand):
    help = (
        "Создаёт тестовых пользователей всех ролей и записывает таблицу "
        "«роль, ФИО, email, пароль» в Markdown-файл. Повторный запуск "
        "обновляет тех же пользователей и выдаёт им новые пароли."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--per-role",
            type=int,
            default=2,
            help="Сколько пользователей создать для каждой роли (по умолчанию 2).",
        )
        parser.add_argument(
            "--output",
            default=str(settings.BASE_DIR / "test_users.md"),
            help="Куда записать таблицу (по умолчанию backend/test_users.md).",
        )

    @transaction.atomic
    def handle(self, *args, per_role, output, **options):
        # Creates superusers with known passwords: never in production
        if not settings.DEBUG:
            raise CommandError("seed_users работает только при DEBUG=True.")
        rows = []
        for role_index, role in enumerate(User.Role):
            for n in range(1, per_role + 1):
                # Name and phone depend only on (role, n), so reruns with another
                # --per-role update the same users instead of clashing on phone
                surname, first_name, patronymic = NAMES[
                    (role_index * 3 + n - 1) % len(NAMES)
                ]
                email = f"{role.value}{n}@example.com"
                password = generate_password()
                user, _ = User.objects.update_or_create(
                    email=email,
                    defaults={
                        "full_name": f"{surname} {first_name} {patronymic}",
                        "phone": f"+79000{role_index + 1}{n:05d}",
                        "role": role,
                        "status": User.Status.ACTIVE,
                        "pd_consent_at": timezone.now(),
                        "is_staff": role == User.Role.ADMIN,
                        "is_superuser": role == User.Role.ADMIN,
                        "failed_attempts": 0,
                        "locked_until": None,
                    },
                )
                user.set_password(password)
                user.save(update_fields=["password"])
                rows.append((role.label, user.full_name, email, password))

        lines = [
            "# Тестовые пользователи",
            "",
            "Сгенерировано командой `python manage.py seed_users`. "
            "Тьюторам и администраторам при первом входе откроется мастер "
            "включения 2FA.",
            "",
            "| Роль | ФИО | Email | Пароль |",
            "| --- | --- | --- | --- |",
            *(f"| {' | '.join(row)} |" for row in rows),
            "",
        ]
        # The table holds passwords: readable by the owner only
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self.stdout.write(
            self.style.SUCCESS(f"Пользователей: {len(rows)}. Таблица: {output}")
        )
