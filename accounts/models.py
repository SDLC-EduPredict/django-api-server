import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from accounts.managers import UserManager
from core.models import TimeStampedModel
from core.validators import employee_code_validator, name_validator, phone_validator

class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        FACULTY = "FACULTY", "Faculty / Staff"
        ADMIN = "ADMIN", "Admin"
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=10, unique=True, null=True, blank=True, validators=[phone_validator])
    first_name = models.CharField(max_length=60, validators=[name_validator])
    last_name = models.CharField(max_length=60, blank=True, validators=[name_validator])
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

    def clean(self) -> None:
        super().clean()
        self.email = self.email.lower()

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

    def apply_role_flags(self) -> None:
        # Only a SUPER_ADMIN may enter the Django admin site (/admin/).
        # The React admin panel does not need is_staff, it uses the role and the permissions.
        is_super_admin = self.role == self.Role.SUPER_ADMIN
        self.is_staff = is_super_admin
        self.is_superuser = is_super_admin


class FacultyProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="faculty_profile")
    employee_code = models.CharField(max_length=10, unique=True, blank=True, validators=[employee_code_validator])
    designation = models.CharField(max_length=100, blank=True)
    expertise = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to="faculty/", blank=True)

    class Meta:
        ordering = ["employee_code"]

    def __str__(self) -> str:
        return f"{self.employee_code} - {self.user.get_full_name() or self.user.email}"

    def save(self, *args, **kwargs):
        if not self.employee_code:
            codes = FacultyProfile.objects.values_list("employee_code", flat=True)
            numbers = [int(code.split("-")[1]) for code in codes]
            self.employee_code = f"FAC-{max(numbers, default=0) + 1:03d}"
        super().save(*args, **kwargs)


class RefreshToken(TimeStampedModel):
    # One row for every refresh token we hand out. The token itself is NOT stored, only its id (jti).
    # This lets us revoke a refresh token (logout, refresh, password change, deactivated user).
    jti = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refresh_tokens")
    expires_at = models.DateTimeField()
    revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} | {self.jti} | {'revoked' if self.revoked else 'active'}"

    @property
    def is_usable(self) -> bool:
        return not self.revoked and self.expires_at > timezone.now()


class OTP(TimeStampedModel):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        SMS = "SMS", "SMS"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    channel = models.CharField(max_length=5, choices=Channel.choices)
    otp_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} | {self.channel}"