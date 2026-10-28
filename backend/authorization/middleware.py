from datetime import timedelta

from django.contrib.auth import logout
from django.utils import timezone

from .models import UserSession

# Avoid a database write on every request
ACTIVITY_UPDATE_INTERVAL = timedelta(minutes=1)


class SessionActivityMiddleware:
    """Track the session's last activity and drop sessions terminated elsewhere.

    A session whose UserSession record was removed (password change, password
    reset, account deletion) is logged out on its next request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            session = UserSession.objects.filter(
                session_key=request.session.session_key, user=request.user
            ).first()
            if session is None:
                logout(request)
            else:
                now = timezone.now()
                if now - session.last_activity_at > ACTIVITY_UPDATE_INTERVAL:
                    session.last_activity_at = now
                    session.save(update_fields=["last_activity_at"])
        return self.get_response(request)
