from django.urls import path

from . import views

app_name = "authorization"

urlpatterns = [
    path("session/", views.SessionView.as_view(), name="session"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("login/2fa/", views.LoginTwoFactorView.as_view(), name="login-2fa"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("me/password/", views.PasswordChangeView.as_view(), name="password-change"),
    path("me/delete/", views.AccountDeleteView.as_view(), name="account-delete"),
    path("2fa/setup/", views.TwoFactorSetupView.as_view(), name="2fa-setup"),
    path("2fa/confirm/", views.TwoFactorConfirmView.as_view(), name="2fa-confirm"),
    path("password-reset/", views.PasswordResetView.as_view(), name="password-reset"),
    path(
        "password-reset/validate/",
        views.PasswordResetValidateView.as_view(),
        name="password-reset-validate",
    ),
    path(
        "password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
]
