from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator

phone_validator = RegexValidator(r"^\+?[0-9]{10,13}$", "Enter a valid phone number (10 to 13 digits, optional leading +).")
student_code_validator = RegexValidator(r"^ABC-\d{4}-\d{4}$", "Student code must look like ABC-2026-0001.")
employee_code_validator = RegexValidator(r"^FAC-\d{3,6}$", "Employee code must look like FAC-001.")
percentage_validators = [MinValueValidator(0), MaxValueValidator(100)]