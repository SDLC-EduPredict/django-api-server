from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
import re
from django.core.exceptions import ValidationError

phone_validator = RegexValidator(r"^[0-9]{10}\Z", "Enter a valid 10 digit phone number. Only digits are allowed (no letters, spaces, + or other special characters).")
name_validator = RegexValidator(r"^[^\W\d_]+(?:[ .'-]+[^\W\d_]+)*\Z", "Name can contain only letters, spaces, dots, hyphens and apostrophes.")
otp_validator = RegexValidator(r"^[0-9]{6}\Z", "OTP must be 6 digits.")
student_code_validator = RegexValidator(r"^ABC-\d{4}-\d{4}\Z", "Student code must look like ABC-2026-0001.")
employee_code_validator = RegexValidator(r"^FAC-\d{3,6}\Z", "Employee code must look like FAC-001.")
percentage_validators = [MinValueValidator(0), MaxValueValidator(100)]


class StrongPasswordValidator:
    RULES = [
        (r"[a-z]", "Password must contain at least one lowercase letter."),
        (r"[A-Z]", "Password must contain at least one uppercase letter."),
        (r"[^A-Za-z0-9\s]", "Password must contain at least one special character (for example @ # $ % & !)."),
    ]

    def validate(self, password, user=None):
        errors = [ValidationError(message, code="password_too_weak") for pattern, message in self.RULES if not re.search(pattern, password)]
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return "Your password must contain at least 6 characters, one uppercase letter, one lowercase letter and one special character."