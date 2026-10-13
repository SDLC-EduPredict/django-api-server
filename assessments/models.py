from django.core.validators import MinValueValidator
from django.db import models
from accounts.models import User
from core.models import TimeStampedModel
from courses.models import Course
from enrolments.models import Enrolment


class Assessment(TimeStampedModel):
    class Type(models.TextChoices):
        MOCK_TEST = "MOCK_TEST", "Mock Test"
        EXAM = "EXAM", "Exam"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assessments")
    title = models.CharField(max_length=150)
    assessment_type = models.CharField(max_length=9, choices=Type.choices, default=Type.MOCK_TEST, db_index=True)
    description = models.TextField(blank=True)
    assessment_date = models.DateField()
    max_marks = models.PositiveSmallIntegerField(default=100, validators=[MinValueValidator(1)])
    pass_marks = models.PositiveSmallIntegerField(default=40)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assessments_created")

    class Meta:
        ordering = ["-assessment_date", "-id"]

    def __str__(self) -> str:
        return f"{self.course.title} - {self.title}"


class AssessmentResult(TimeStampedModel):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="results")
    enrolment = models.ForeignKey(Enrolment, on_delete=models.CASCADE, related_name="assessment_results")
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    remarks = models.CharField(max_length=255, blank=True)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="results_entered")

    class Meta:
        ordering = ["enrolment__student__student_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "enrolment"],
                name="unique_assessment_result",
                violation_error_message="This student already has a result for this assessment."),
        ]

    def __str__(self) -> str:
        return f"{self.assessment.title} | {self.enrolment.student.student_code} | {self.marks_obtained}"

    @property
    def percentage(self) -> float:
        return round(float(self.marks_obtained) * 100 / self.assessment.max_marks, 2)

    @property
    def result(self) -> str:
        return "PASS" if self.marks_obtained >= self.assessment.pass_marks else "FAIL"
