# Generated for the homework module.
import django.db.models.deletion
from django.db import migrations, models

import homework.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("course", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="HomeworkReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_date", models.DateField(verbose_name="Дата отчета")),
                ("status", models.CharField(
                    choices=[("filling", "Заполняется"), ("review", "Проверяется"), ("reviewed", "Проверен")],
                    default="filling", max_length=12, verbose_name="Статус"
                )),
                ("participant_comment", models.TextField(blank=True, verbose_name="Комментарий участника")),
                ("tutor_comment", models.TextField(blank=True, verbose_name="Комментарий тьютора")),
                ("is_completed", models.BooleanField(
                    blank=True, help_text="Заполняется тьютором при проверке.",
                    null=True, verbose_name="Выполнено"
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Изменен")),
                ("submitted_at", models.DateTimeField(blank=True, null=True, verbose_name="Отправлен на проверку")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True, verbose_name="Проверен")),
                ("participant", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="homework_reports", to="course.participant",
                    verbose_name="Участник курса"
                )),
            ],
            options={
                "verbose_name": "отчет по домашнему заданию",
                "verbose_name_plural": "отчеты по домашним заданиям",
                "ordering": ["report_date", "pk"],
            },
        ),
        migrations.CreateModel(
            name="MealEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("water_drank", models.BooleanField(verbose_name="Выпит стакан воды")),
                ("breathing_practice", models.BooleanField(verbose_name="Выполнена дыхательная практика")),
                ("feeling", models.CharField(
                    choices=[("hunger", "Голод"), ("appetite", "Аппетит")],
                    max_length=8, verbose_name="Ощущение перед приемом"
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Добавлен")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Изменен")),
                ("report", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="meals", to="homework.homeworkreport",
                    verbose_name="Отчет"
                )),
            ],
            options={
                "verbose_name": "прием пищи",
                "verbose_name_plural": "приемы пищи",
                "ordering": ["created_at", "pk"],
            },
        ),
        migrations.CreateModel(
            name="MealPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.FileField(upload_to=homework.models.meal_photo_upload_to, verbose_name="Фото блюда")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True, verbose_name="Загружено")),
                ("meal", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="photos", to="homework.mealentry",
                    verbose_name="Прием пищи"
                )),
            ],
            options={
                "verbose_name": "фото блюда",
                "verbose_name_plural": "фотографии блюд",
            },
        ),
        migrations.AddConstraint(
            model_name="homeworkreport",
            constraint=models.UniqueConstraint(
                fields=("participant", "report_date"),
                name="one_homework_report_per_participant_day",
            ),
        ),
        migrations.AddConstraint(
            model_name="homeworkreport",
            constraint=models.CheckConstraint(
                condition=models.Q(("is_completed__isnull", False), ("status", "reviewed"))
                | ~models.Q(("status", "reviewed")),
                name="homework_reviewed_has_grade",
            ),
        ),
        migrations.AddIndex(
            model_name="homeworkreport",
            index=models.Index(fields=["status", "report_date"], name="homework_h_status_7acb11_idx"),
        ),
    ]
