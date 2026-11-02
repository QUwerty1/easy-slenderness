from django.urls import reverse
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from .models import PHOTO_FORMATS, HomeworkReport, MealEntry, MealPhoto


class MealPhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = MealPhoto
        fields = ("id", "url", "uploaded_at")

    def get_url(self, photo):
        # Relative URL: the client reaches the API through its own /api proxy.
        return reverse("homework:photo", kwargs={"photo_id": photo.pk})


class MealEntrySerializer(serializers.ModelSerializer):
    feeling_display = serializers.CharField(
        source="get_feeling_display", read_only=True
    )
    photos = MealPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = MealEntry
        fields = (
            "id",
            "water_drank",
            "breathing_practice",
            "feeling",
            "feeling_display",
            "photos",
            "created_at",
            "updated_at",
        )


class HomeworkReportSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    meals = MealEntrySerializer(many=True, read_only=True)
    meal_count = serializers.IntegerField(source="meals.count", read_only=True)

    class Meta:
        model = HomeworkReport
        fields = (
            "id",
            "report_date",
            "status",
            "status_display",
            "participant_comment",
            "tutor_comment",
            "is_completed",
            "created_at",
            "submitted_at",
            "reviewed_at",
            "meal_count",
            "meals",
        )


class ImageFileField(serializers.FileField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "Размер одного изображения не должен превышать 10 МБ."
            )
        # Content-Type и имя файла задает клиент, поэтому формат определяется
        # по содержимому: принимаются только JPEG, PNG и WebP.
        try:
            with Image.open(value) as image:
                image_format = image.format
                image.verify()
        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            ValueError,
            Image.DecompressionBombError,
        ):
            raise serializers.ValidationError(
                "Можно загружать только изображения."
            ) from None
        finally:
            value.seek(0)
        if image_format not in PHOTO_FORMATS:
            raise serializers.ValidationError(
                "Поддерживаются только изображения JPEG, PNG и WebP."
            )
        ext, content_type = PHOTO_FORMATS[image_format]
        value.name = f"photo{ext}"
        value.content_type = content_type
        return value


class MealCreateSerializer(serializers.Serializer):
    water_drank = serializers.BooleanField()
    breathing_practice = serializers.BooleanField()
    feeling = serializers.ChoiceField(choices=MealEntry.Feeling.choices)
    photos = serializers.ListField(
        child=ImageFileField(),
        allow_empty=False,
        min_length=1,
        max_length=10,
        write_only=True,
    )


class MealUpdateSerializer(serializers.Serializer):
    water_drank = serializers.BooleanField()
    breathing_practice = serializers.BooleanField()
    feeling = serializers.ChoiceField(choices=MealEntry.Feeling.choices)
    photos = serializers.ListField(
        child=ImageFileField(),
        allow_empty=False,
        min_length=1,
        required=False,
        write_only=True,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Укажите данные для изменения.")
        return attrs


class ParticipantCommentSerializer(serializers.Serializer):
    participant_comment = serializers.CharField(allow_blank=True)


class ReviewSerializer(serializers.Serializer):
    tutor_comment = serializers.CharField(allow_blank=True, required=False, default="")
    is_completed = serializers.BooleanField()
