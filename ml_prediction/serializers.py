from rest_framework import serializers
from enrolments.serializers import CourseShortSerializer, StudentShortSerializer
from ml_prediction.models import MLModelVersion, Prediction


class MLModelVersionShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLModelVersion
        fields = ("id", "name", "algorithm", "r2_score", "rmse", "created_at")
        read_only_fields = fields


class MLModelVersionSerializer(serializers.ModelSerializer):
    data_source_display = serializers.CharField(source="get_data_source_display", read_only=True)
    trained_by = serializers.CharField(source="trained_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = MLModelVersion
        fields = (
            "id", "name", "version", "algorithm", "is_active", "data_source", "data_source_display", "source_name",
            "features", "target", "total_rows", "cleaned_rows", "training_rows", "test_rows",
            "mae", "mse", "rmse", "r2_score", "intercept", "coefficients", "feature_means", "correlations",
            "trained_by", "created_at")
        read_only_fields = fields


class PredictionSerializer(serializers.ModelSerializer):
    attendance = serializers.FloatField(read_only=True)
    assignment_average = serializers.FloatField(read_only=True)
    mock_test_average = serializers.FloatField(read_only=True)
    practice_hours = serializers.FloatField(read_only=True)
    previous_score = serializers.FloatField(read_only=True)
    modules_completed = serializers.FloatField(read_only=True)
    predicted_final_score = serializers.FloatField(read_only=True)
    indicator_display = serializers.CharField(source="get_indicator_display", read_only=True)
    model_version = MLModelVersionShortSerializer(read_only=True)

    class Meta:
        model = Prediction
        fields = (
            "id", "predicted_final_score", "indicator", "indicator_display",
            "attendance", "assignment_average", "mock_test_average", "practice_hours", "previous_score", "modules_completed",
            "model_version", "updated_at")
        read_only_fields = fields


class StaffPredictionSerializer(PredictionSerializer):
    student = StudentShortSerializer(source="enrolment.student", read_only=True)
    course = CourseShortSerializer(source="enrolment.course", read_only=True)
    enrolment_status = serializers.CharField(source="enrolment.status", read_only=True)

    class Meta(PredictionSerializer.Meta):
        fields = ("id", "enrolment", "enrolment_status", "student", "course") + PredictionSerializer.Meta.fields[1:]
        read_only_fields = fields