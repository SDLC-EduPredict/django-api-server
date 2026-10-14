from django.db import models
from accounts.models import User
from core.models import TimeStampedModel
from enrolments.models import Enrolment


class Attendance(TimeStampedModel):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        LATE = "LATE", "Late"
        ABSENT = "ABSENT", "Absent"

    enrolment = models.ForeignKey(Enrolment, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=7, choices=Status.choices)
    remarks = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_marked")

    ATTENDED = [Status.PRESENT, Status.LATE]

    class Meta:
        ordering = ["-date", "enrolment__student__student_code"]
        verbose_name_plural = "attendance"
        constraints = [
            models.UniqueConstraint(
                fields=["enrolment", "date"],
                name="unique_attendance_per_day",
                violation_error_message="Attendance for this student on this date is already recorded."),
        ]

    def __str__(self) -> str:
        return f"{self.enrolment} | {self.date} | {self.status}"
