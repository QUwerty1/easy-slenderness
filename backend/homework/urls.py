from django.urls import path

from . import views

app_name = "homework"

urlpatterns = [
    path(
        "courses/<int:course_id>/homework/reports/",
        views.ReportListView.as_view(),
        name="report-list",
    ),
    path(
        "courses/<int:course_id>/homework/reports/<str:report_date>/",
        views.ReportDateView.as_view(),
        name="report-date",
    ),
    path(
        "courses/<int:course_id>/homework/reports/<str:report_date>/meals/",
        views.MealCreateView.as_view(),
        name="meal-create",
    ),
    path(
        "courses/<int:course_id>/homework/meals/<int:meal_id>/",
        views.MealDetailView.as_view(),
        name="meal-detail",
    ),
    path(
        "courses/<int:course_id>/homework/reports/<int:report_id>/review/",
        views.TutorReviewView.as_view(),
        name="report-review",
    ),
    path(
        "homework/photos/<int:photo_id>/",
        views.MealPhotoView.as_view(),
        name="photo",
    ),
]
