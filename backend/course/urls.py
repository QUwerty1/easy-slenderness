from django.urls import path

from . import views

app_name = "course"

urlpatterns = [
    path("courses/", views.CourseListView.as_view(), name="list"),
    path("courses/available/", views.AvailableCoursesView.as_view(), name="available"),
    path("courses/my/", views.MyCoursesView.as_view(), name="my"),
    path("courses/<int:pk>/", views.CourseDetailView.as_view(), name="detail"),
    path("courses/<int:pk>/enroll/", views.EnrollView.as_view(), name="enroll"),
    path(
        "courses/<int:pk>/enrollment/",
        views.EnrollmentStatusView.as_view(),
        name="enrollment",
    ),
    path(
        "courses/<int:pk>/participants/",
        views.ParticipantsView.as_view(),
        name="participants",
    ),
    path(
        "courses/<int:pk>/candidates/",
        views.CandidatesView.as_view(),
        name="candidates",
    ),
    path(
        "courses/<int:pk>/manual-enroll/",
        views.ManualEnrollView.as_view(),
        name="manual-enroll",
    ),
    path("participants/<int:pk>/exclude/", views.ExcludeView.as_view(), name="exclude"),
    path("payments/webhook/", views.PaymentWebhookView.as_view(), name="webhook"),
    path("payments/fake/", views.FakePaymentView.as_view(), name="fake-payment"),
    path("requests/", views.RequestListView.as_view(), name="requests"),
    path("requests/my/", views.MyRequestsView.as_view(), name="my-requests"),
    path("requests/refusable/", views.RefusableView.as_view(), name="refusable"),
    path("requests/<int:pk>/", views.RequestDetailView.as_view(), name="request"),
    path(
        "requests/<int:pk>/refund/",
        views.RequestRefundView.as_view(),
        name="request-refund",
    ),
    path(
        "requests/<int:pk>/close/",
        views.RequestCloseView.as_view(),
        name="request-close",
    ),
    path(
        "requests/<int:pk>/reject/",
        views.RequestRejectView.as_view(),
        name="request-reject",
    ),
]
