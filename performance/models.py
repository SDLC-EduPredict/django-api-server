from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from accounts.models import User
from core.models import TimeStampedModel
from core.validators import percentage_validators
from enrolments.models import Enrolment


class Performance(TimeStampedModel):
    class Participation(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    class Indicator(models.TextChoices):
        GOOD = "GOOD", "Good"
        AVERAGE = "AVERAGE", "Average"
        NEEDS_ATTENTION = "NEEDS_ATTENTION", "Needs Attention"
        NO_DATA = "NO_DATA", "Not enough data"

    PARTICIPATION_SCORES = {Participation.LOW: 1, Participation.MEDIUM: 2, Participation.HIGH: 3}

    enrolment = models.OneToOneField(Enrolment, on_delete=models.CASCADE, related_name="performance")

    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    assignment_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    mock_test_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    exam_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    assessment_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    modules_completed_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    indicator = models.CharField(max_length=15, choices=Indicator.choices, default=Indicator.NO_DATA, db_index=True)
    calculated_at = models.DateTimeField(null=True, blank=True)

    practice_hours = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(168)])
    previous_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=percentage_validators)
    modules_completed = models.PositiveSmallIntegerField(null=True, blank=True)
    participation = models.CharField(max_length=6, choices=Participation.choices, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="performances_updated")

    CALCULATED_FIELDS = [
        "attendance_percentage", "assignment_average", "mock_test_average", "exam_average", "assessment_average",
        "modules_completed_percentage", "overall_score", "indicator", "calculated_at",
    ]

    class Meta:
        ordering = ["enrolment__course__title", "enrolment__student__student_code"]

    def __str__(self) -> str:
        return f"{self.enrolment} | {self.overall_score} | {self.indicator}"

    def clean(self) -> None:
        super().clean()
        total_modules = self.enrolment.course.total_modules
        if self.modules_completed is not None and self.modules_completed > total_modules:
            raise ValidationError({"modules_completed": f"This course has only {total_modules} modules."})

    @property
    def participation_score(self):
        return self.PARTICIPATION_SCORES.get(self.participation)