from django.db import models
from django.utils import timezone
from accounts.models import User
from core.models import TimeStampedModel
from core.validators import name_validator, student_code_validator


class StudentProfile(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"
        OTHER = "OTHER", "Other"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    student_code = models.CharField(max_length=13, unique=True, blank=True, validators=[student_code_validator])
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=6, choices=Gender.choices, blank=True)
    highest_qualification = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=60, blank=True, validators=[name_validator])
    photo = models.ImageField(upload_to="students/", blank=True)

    PROFILE_FIELDS = ["date_of_birth", "gender", "highest_qualification", "address", "city", "photo"]

    class Meta:
        ordering = ["student_code"]

    def __str__(self) -> str:
        return f"{self.student_code} - {self.user.get_full_name() or self.user.email}"

    def save(self, *args, **kwargs):
        if not self.student_code:
            prefix = f"ABC-{timezone.now().year}-"
            codes = StudentProfile.objects.filter(student_code__startswith=prefix).values_list("student_code", flat=True)
            numbers = [int(code[len(prefix):]) for code in codes]
            self.student_code = f"{prefix}{max(numbers, default=0) + 1:04d}"
        super().save(*args, **kwargs)

    @property
    def missing_profile_fields(self) -> list[str]:
        missing = [field for field in self.PROFILE_FIELDS if not getattr(self, field)]
        if not self.user.phone:
            missing.append("phone")
        return missing

    @property
    def profile_completion(self) -> int:
        total = len(self.PROFILE_FIELDS) + 1
        filled = total - len(self.missing_profile_fields)
        return round(filled * 100 / total)