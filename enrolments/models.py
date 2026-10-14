from datetime import timedelta
from django.db import models
from django.utils import timezone
from core.models import TimeStampedModel
from courses.models import Course
from students.models import StudentProfile


class Enrolment(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        DROPPED = "DROPPED", "Dropped"

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="enrolments")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="enrolments")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    enrolled_on = models.DateField(default=timezone.localdate)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-enrolled_on", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"],
                name="unique_student_course_enrolment",
                violation_error_message="This student is already enrolled in this course."),
        ]

    def __str__(self) -> str:
        return f"{self.student.student_code} - {self.course.title}"

    def save(self, *args, **kwargs):
        if not self.start_date:
            course_start = self.course.start_date
            self.start_date = max(course_start, self.enrolled_on) if course_start else self.enrolled_on
        if not self.end_date:
            self.end_date = self.start_date + timedelta(weeks=self.course.duration_weeks)
        super().save(*args, **kwargs)

    def has_academic_records(self) -> bool:
        return self.attendance_records.exists() or self.submissions.exists() or self.assessment_results.exists()
