from django.db import models
from django.utils import timezone
from accounts.models import User
from core.models import TimeStampedModel
from courses.models import Course


class Notification(TimeStampedModel):
    class Type(models.TextChoices):
        COURSE = "COURSE", "Course"
        ASSIGNMENT = "ASSIGNMENT", "Assignment"
        ASSESSMENT = "ASSESSMENT", "Assessment"
        ACADEMIC_ALERT = "ACADEMIC_ALERT", "Academic Alert"
        ADMINISTRATIVE = "ADMINISTRATIVE", "Administrative"

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=14, choices=Type.choices, default=Type.ADMINISTRATIVE, db_index=True)
    title = models.CharField(max_length=150)
    message = models.TextField()
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications_sent")
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.recipient.email} | {self.title}"

    def mark_as_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])