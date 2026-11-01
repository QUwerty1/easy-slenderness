from django.contrib import admin

from .models import Course, ExclusionRequest, Participant, Payment, Refund


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "price", "start_at", "end_at", "state")
    list_filter = ("status", "state")
    search_fields = ("name",)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "enrolled_at", "method", "status")
    list_filter = ("status", "method", "course")
    search_fields = ("user__email", "user__full_name", "course__name")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("participant", "method", "amount", "paid_at", "transaction_id")
    list_filter = ("method",)


@admin.register(ExclusionRequest)
class ExclusionRequestAdmin(admin.ModelAdmin):
    list_display = ("participant", "basis", "created_at", "status")
    list_filter = ("status", "basis")
    readonly_fields = ("created_at",)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("request", "amount", "fpr", "refunded_at")
