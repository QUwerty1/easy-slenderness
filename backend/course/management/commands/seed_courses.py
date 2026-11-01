from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from authorization.models import User
from course import services
from course.models import Course, ExclusionRequest, Participant, Payment

# (name, status, price, start offset in days)
COURSES = [
    ("Перезагрузка питания", Course.Status.PAID, "4900", 5),
    ("Лёгкий старт", Course.Status.FREE, None, 7),
    ("Стройность за месяц", Course.Status.PAID, "5900", -10),
    ("Сахар под контролем", Course.Status.FREE, None, -3),
    ("Весенний марафон", Course.Status.PAID, "4500", -40),
]


class Command(BaseCommand):
    help = (
        "Создаёт демонстрационные курсы, участников, платежи и заявки. "
        "Сначала выполните seed_users: участниками становятся пользователи с ролью "
        "«Пользователь» или «Участник курса»."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        learners = list(
            User.objects.filter(role__in=services.LEARNER_ROLES).order_by("pk")
        )
        if len(learners) < 2:
            self.stderr.write("Нужно хотя бы два пользователя: выполните seed_users.")
            return
        courses = []
        for name, status, price, days in COURSES:
            start = (now + timedelta(days=days)).replace(
                hour=10, minute=0, second=0, microsecond=0
            )
            course, _ = Course.objects.update_or_create(
                name=name,
                defaults={
                    "status": status,
                    "price": Decimal(price) if price else None,
                    "start_at": start,
                    "end_at": Course.end_for(status, start),
                    "state": Course.State.OPEN,
                },
            )
            courses.append(course)
        services.update_states(now)

        _, _, running_paid, running_free, archived = courses
        for course in (running_paid, running_free, archived):
            for user in learners:
                participant, created = Participant.objects.get_or_create(
                    user=user,
                    course=course,
                    status=Participant.Status.ACTIVE,
                    defaults={"method": Participant.Method.SELF},
                )
                if created and course.is_paid:
                    Payment.objects.create(
                        participant=participant,
                        method=Payment.Method.SERVICE,
                        amount=course.price,
                        paid_at=course.start_at - timedelta(days=3),
                        transaction_id=f"demo-{participant.pk}",
                    )
        # A registered request of the first learner in the running paid course
        first = running_paid.participants.get(user=learners[0], status="active")
        if not first.requests.exists():
            ExclusionRequest.objects.create(
                participant=first,
                basis=ExclusionRequest.Basis.PARTICIPANT,
                reason="Не успеваю по времени",
            )
        for user in learners:
            services.sync_role(user)
        self.stdout.write(self.style.SUCCESS(f"Курсов: {len(courses)}"))
