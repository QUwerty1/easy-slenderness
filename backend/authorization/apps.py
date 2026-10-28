from django.apps import AppConfig


class AuthorizationConfig(AppConfig):
    name = "authorization"
    verbose_name = "Авторизация"

    def ready(self):
        from . import signals  # noqa: F401
