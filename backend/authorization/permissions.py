from rest_framework.permissions import BasePermission

from .services import PRE_AUTH_KEY, SETUP_2FA_KEY


class IsGuest(BasePermission):
    message = "Действие доступно только неавторизованным пользователям."

    def has_permission(self, request, view):
        return not request.user.is_authenticated


class IsPreAuth(BasePermission):
    """Password checked, waiting for the 2FA code."""

    message = "Сначала войдите с email и паролем."

    def has_permission(self, request, view):
        return PRE_AUTH_KEY in request.session


class IsAuthOrSetup2FA(BasePermission):
    """Logged in, or a tutor/administrator who must enable 2FA before logging in."""

    def has_permission(self, request, view):
        return request.user.is_authenticated or SETUP_2FA_KEY in request.session
