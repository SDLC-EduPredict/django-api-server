from django.contrib.auth import get_user_model
from django.test import TestCase
from accounts.models import FacultyProfile

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_defaults_to_student_and_lowercases_email(self) -> None:
        user = User.objects.create_user("Rahul@Example.com", "pass12345!", first_name="Rahul")
        self.assertEqual(user.email, "rahul@example.com")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.check_password("pass12345!"))
        self.assertFalse(user.is_staff)

    def test_create_superuser_gets_super_admin_role(self) -> None:
        user = User.objects.create_superuser("root@example.com", "pass12345!", first_name="Root")
        self.assertEqual(user.role, User.Role.SUPER_ADMIN)
        self.assertTrue(user.is_staff and user.is_superuser)

    def test_email_is_required(self) -> None:
        with self.assertRaises(ValueError):
            User.objects.create_user("", "pass12345!")

    def test_blank_phone_numbers_do_not_clash(self) -> None:
        User.objects.create_user("a@example.com", "pass12345!", first_name="A")
        User.objects.create_user("b@example.com", "pass12345!", first_name="B")
        self.assertEqual(User.objects.filter(phone__isnull=True).count(), 2)

    def test_faculty_profile_string(self) -> None:
        user = User.objects.create_user("f@example.com", "pass12345!", first_name="Fay", role=User.Role.FACULTY)
        profile = FacultyProfile.objects.create(user=user, employee_code="FAC-001")
        self.assertIn("FAC-001", str(profile))
