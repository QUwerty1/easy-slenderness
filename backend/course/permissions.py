from rest_framework.permissions import BasePermission

from . import services


class IsAdmin(BasePermission):
    message = "Действие доступно только администратору."

    def has_permission(self, request, view):
        return services.is_admin(request.user)


class IsLearner(BasePermission):
    message = "Действие доступно только пользователю."

    def has_permission(self, request, view):
        return services.is_learner(request.user)


class IsAdminOrTutor(BasePermission):
    message = "Действие доступно только администратору и тьютору."

    def has_permission(self, request, view):
        return services.is_admin(request.user) or services.is_tutor(request.user)
