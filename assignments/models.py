from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from accounts.models import User
from core.models import TimeStampedModel
from courses.models import Course
from enrolments.models import Enrolment

SUBMISSION_FILE_TYPES = ["pdf", "doc", "docx", "txt", "zip", "py", "ipynb", "jpg", "jpeg", "png"]


class Assignment(TimeStampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    max_marks = models.PositiveSmallIntegerField(default=100, validators=[MinValueValidator(1)])
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assignments_created")

    class Meta:
        ordering = ["-due_date", "-id"]

    def __str__(self) -> str:
        return f"{self.course.title} - {self.title}"


class AssignmentSubmission(TimeStampedModel):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        GRADED = "GRADED", "Graded"

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    enrolment = models.ForeignKey(Enrolment, on_delete=models.CASCADE, related_name="submissions")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    submission_text = models.TextField(blank=True)
    submission_link = models.URLField(blank=True)
    submission_file = models.FileField(upload_to="assignments/", blank=True, validators=[FileExtensionValidator(SUBMISSION_FILE_TYPES)])
    submitted_at = models.DateTimeField(null=True, blank=True)
    marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="submissions_graded")
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "enrolment"],
                name="unique_assignment_submission",
                violation_error_message="This student already has a submission for this assignment."),
        ]

    def __str__(self) -> str:
        return f"{self.assignment.title} | {self.enrolment.student.student_code} | {self.status}"

    @property
    def is_late(self) -> bool:
        return bool(self.submitted_at) and self.submitted_at.date() > self.assignment.due_date

    @property
    def percentage(self):
        if self.marks is None:
            return None
        return round(float(self.marks) * 100 / self.assignment.max_marks, 2)
