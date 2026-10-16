from django.contrib import admin
from ml_prediction.models import MLModelVersion, Prediction


@admin.register(MLModelVersion)
class MLModelVersionAdmin(admin.ModelAdmin):
    list_display = ("name", "algorithm", "is_active", "data_source", "cleaned_rows", "mae", "rmse", "r2_score", "trained_by", "created_at")
    list_filter = ("is_active", "data_source")
    readonly_fields = [field.name for field in MLModelVersion._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "predicted_final_score", "indicator", "model_version", "updated_at")
    list_filter = ("indicator", "model_version", "enrolment__course")
    search_fields = ("enrolment__student__student_code", "enrolment__student__user__first_name", "enrolment__student__user__last_name", "enrolment__course__title")
    list_select_related = ("enrolment__student__user", "enrolment__course", "model_version")
    readonly_fields = [field.name for field in Prediction._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False