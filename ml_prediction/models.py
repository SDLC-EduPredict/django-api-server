from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from accounts.models import User
from core.models import TimeStampedModel
from core.validators import percentage_validators
from enrolments.models import Enrolment
from performance.models import Performance


class MLModelVersion(TimeStampedModel):
    class DataSource(models.TextChoices):
        SAMPLE = "SAMPLE", "Sample historical dataset"
        CSV = "CSV", "Uploaded CSV file"
        DATABASE = "DATABASE", "Performance records in the database"

    version = models.PositiveIntegerField(unique=True)
    algorithm = models.CharField(max_length=50, default="Linear Regression")
    file_name = models.CharField(max_length=100)
    data_source = models.CharField(max_length=8, choices=DataSource.choices)
    source_name = models.CharField(max_length=255, blank=True)
    features = models.JSONField(default=list)
    target = models.CharField(max_length=50)
    total_rows = models.PositiveIntegerField()
    cleaned_rows = models.PositiveIntegerField()
    training_rows = models.PositiveIntegerField()
    test_rows = models.PositiveIntegerField()
    mae = models.FloatField()
    mse = models.FloatField()
    rmse = models.FloatField()
    r2_score = models.FloatField()
    intercept = models.FloatField()
    coefficients = models.JSONField(default=dict)
    feature_means = models.JSONField(default=dict)
    correlations = models.JSONField(default=dict)
    is_active = models.BooleanField(default=False, db_index=True)
    trained_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="ml_models_trained")

    class Meta:
        ordering = ["-version"]
        verbose_name = "ML model version"

    def __str__(self) -> str:
        status = " | active" if self.is_active else ""
        return f"{self.name} | R2 {self.r2_score:.3f}{status}"

    @property
    def name(self) -> str:
        return f"v{self.version}"


class Prediction(TimeStampedModel):
    enrolment = models.OneToOneField(Enrolment, on_delete=models.CASCADE, related_name="prediction")
    model_version = models.ForeignKey(MLModelVersion, on_delete=models.PROTECT, related_name="predictions")

    attendance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=percentage_validators)
    assignment_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=percentage_validators)
    mock_test_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=percentage_validators)
    practice_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(168)])
    previous_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=percentage_validators)
    modules_completed = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=percentage_validators)

    predicted_final_score = models.DecimalField(max_digits=5, decimal_places=2)
    indicator = models.CharField(max_length=15, choices=Performance.Indicator.choices, db_index=True)

    FEATURES = ["attendance", "assignment_average", "mock_test_average", "practice_hours", "previous_score", "modules_completed"]

    class Meta:
        ordering = ["enrolment__course__title", "enrolment__student__student_code"]

    def __str__(self) -> str:
        return f"{self.enrolment} | {self.predicted_final_score} | {self.indicator}"

    def feature_values(self) -> dict:
        values = {feature: getattr(self, feature) for feature in self.FEATURES}
        return {feature: None if value is None else round(float(value), 2) for feature, value in values.items()}