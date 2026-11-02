from django.contrib import admin

from .models import HomeworkReport, MealEntry, MealPhoto


class MealPhotoInline(admin.TabularInline):
    model = MealPhoto
    extra = 0


class MealEntryInline(admin.TabularInline):
    model = MealEntry
    extra = 0


@admin.register(HomeworkReport)
class HomeworkReportAdmin(admin.ModelAdmin):
    list_display = ("id", "participant", "report_date", "status", "is_completed")
    list_filter = ("status", "report_date", "is_completed")
    search_fields = ("participant__user__full_name", "participant__user__email")
    inlines = (MealEntryInline,)


@admin.register(MealEntry)
class MealEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "water_drank", "breathing_practice", "feeling")
    inlines = (MealPhotoInline,)


@admin.register(MealPhoto)
class MealPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "meal", "uploaded_at")
