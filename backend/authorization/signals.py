from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import UserSession


@receiver(user_logged_in)
def create_user_session(sender, request, user, **kwargs):
    if not request.session.session_key:
        request.session.save()
    UserSession.objects.update_or_create(
        session_key=request.session.session_key,
        defaults={
            "user": user,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
            "ip": request.META.get("REMOTE_ADDR") or None,
        },
    )


@receiver(user_logged_out)
def delete_user_session(sender, request, user, **kwargs):
    if request is not None and request.session.session_key:
        UserSession.objects.filter(session_key=request.session.session_key).delete()
