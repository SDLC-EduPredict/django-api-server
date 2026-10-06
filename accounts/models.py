import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from accounts.managers import UserManager
from core.models import TimeStampedModel
from core.validators import employee_code_validator, phone_validator

class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        FACULTY = "FACULTY", "Faculty / Staff"
        ADMIN = "ADMIN", "Admin"
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True, validators=[phone_validator])
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60, blank=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.STUDENT, db_index=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name"]

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        return self.first_name

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    @property
    def is_faculty(self) -> bool:
        return self.role == self.Role.FACULTY

    @property
    def is_admin_role(self) -> bool:
        return self.role in (self.Role.ADMIN, self.Role.SUPER_ADMIN)


class FacultyProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="faculty_profile")
    employee_code = models.CharField(max_length=10, unique=True, validators=[employee_code_validator])
    designation = models.CharField(max_length=100, blank=True)
    expertise = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to="faculty/", blank=True)

    class Meta:
        ordering = ["employee_code"]

    def __str__(self) -> str:
        return f"{self.employee_code} - {self.user.get_full_name() or self.user.email}"