import shutil
import tempfile
from datetime import timedelta
from io import BytesIO, StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from accounts.tokens import create_access_token
from courses.models import Course, CourseCategory
from permissions.models import RolePermission
from students.models import StudentProfile
from students.signals import create_missing_student_profiles

PASSWORD = "Str0ng-Pass-123!"
MEDIA_ROOT = tempfile.mkdtemp()
YEAR = timezone.now().year


def image_file(name="photo.png"):
    buffer = BytesIO()
    Image.new("RGB", (10, 10), "red").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class StudentTestData(TestCase):
    def setUp(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        self.client = APIClient()
        self.student = User.objects.create_user("rahul@gmail.com", PASSWORD, first_name="Rahul", last_name="Sen")
        self.other = User.objects.create_user("ananya@gmail.com", PASSWORD, first_name="Ananya", phone="9000000001")
        self.faculty = User.objects.create_user("fay@gmail.com", PASSWORD, first_name="Fay", role=User.Role.FACULTY)
        self.admin = User.objects.create_user("manager@gmail.com", PASSWORD, first_name="Manager", role=User.Role.ADMIN)

    def act_as(self, user) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_access_token(user)}")


class StudentProfileModelTests(StudentTestData):
    def test_profile_and_student_code_are_created_for_students_only(self) -> None:
        self.assertEqual(self.student.student_profile.student_code, f"ABC-{YEAR}-0001")
        self.assertEqual(self.other.student_profile.student_code, f"ABC-{YEAR}-0002")
        self.assertEqual(StudentProfile.objects.count(), 2)

    def test_registration_creates_the_profile(self) -> None:
        data = {
            "email": "sourav@gmail.com", "first_name": "Sourav", "last_name": "Paul", "phone": "9000000002",
            "password": PASSWORD, "confirm_password": PASSWORD, "role": "STUDENT",
        }
        self.assertEqual(self.client.post("/api/auth/register/", data, format="json").status_code, 201)
        self.assertEqual(User.objects.get(email="sourav@gmail.com").student_profile.student_code, f"ABC-{YEAR}-0003")

    def test_students_created_before_phase_3_get_a_profile_after_migrate(self) -> None:
        StudentProfile.objects.filter(user=self.student).delete()
        create_missing_student_profiles(sender=None)
        self.assertTrue(StudentProfile.objects.filter(user=self.student).exists())

    def test_profile_completion(self) -> None:
        profile = self.other.student_profile
        self.assertEqual(profile.profile_completion, 14)
        self.assertIn("city", profile.missing_profile_fields)
        self.assertNotIn("phone", profile.missing_profile_fields)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class StudentProfileApiTests(StudentTestData):
    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_get_own_profile(self) -> None:
        self.act_as(self.student)
        response = self.client.get("/api/student/profile/")
        self.assertEqual(response.status_code, 200)
        profile = response.json()["data"]["profile"]
        self.assertEqual((profile["student_code"], profile["user"]["email"]), (f"ABC-{YEAR}-0001", "rahul@gmail.com"))
        self.assertNotIn("password", profile["user"])

    def test_only_students_can_use_it(self) -> None:
        self.assertEqual(self.client.get("/api/student/profile/").status_code, 401)
        for user in (self.faculty, self.admin):
            self.act_as(user)
            self.assertEqual(self.client.get("/api/student/profile/").status_code, 403)

    def test_patch_updates_profile_and_user_fields(self) -> None:
        self.act_as(self.student)
        data = {"date_of_birth": "2003-05-14", "gender": "MALE", "city": "Kolkata", "phone": "9876543210", "student_code": "ABC-2020-9999"}
        response = self.client.patch("/api/student/profile/", data, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        profile = response.json()["data"]["profile"]
        self.assertEqual((profile["city"], profile["gender_display"], profile["user"]["phone"]), ("Kolkata", "Male", "9876543210"))
        self.assertEqual(profile["student_code"], f"ABC-{YEAR}-0001")
        self.assertEqual(profile["user"]["last_name"], "Sen")
        self.assertEqual(profile["profile_completion"], 57)

    def test_patch_photo(self) -> None:
        self.act_as(self.student)
        response = self.client.patch("/api/student/profile/", {"photo": image_file()}, format="multipart")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertIn("/media/students/", response.json()["data"]["profile"]["photo"])
        again = self.client.patch("/api/student/profile/", {"city": "Howrah"}, format="json")
        self.assertIn("/media/students/", again.json()["data"]["profile"]["photo"])

    def test_patch_validation_errors(self) -> None:
        self.act_as(self.student)
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        data = {"date_of_birth": tomorrow, "gender": "X", "city": "K0lkata", "phone": "9000000001", "photo": "not-a-file"}
        response = self.client.patch("/api/student/profile/", data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()["errors"]), {"date_of_birth", "gender", "city", "phone"})

    def test_dashboard(self) -> None:
        category = CourseCategory.objects.create(name="Programming")
        for number in range(5):
            Course.objects.create(category=category, title=f"Course {number}", short_description="x", duration_weeks=4, total_modules=4, status=Course.Status.PUBLISHED)
        Course.objects.create(category=category, title="Hidden", short_description="x", duration_weeks=4, total_modules=4)

        self.act_as(self.student)
        response = self.client.get("/api/student/dashboard/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["summary"], {"profile_completion": 0, "email_verified": False, "available_courses": 5, "enrolled_courses": 0, "completed_courses": 0, "course_categories": 1})
        self.assertEqual(len(data["latest_courses"]), 4)
        self.assertNotIn("Hidden", [course["title"] for course in data["latest_courses"]])
        self.act_as(self.faculty)
        self.assertEqual(self.client.get("/api/student/dashboard/").status_code, 403)


class AdminStudentApiTests(StudentTestData):
    def test_only_admins_can_see_students(self) -> None:
        self.assertEqual(self.client.get("/api/admin/students/").status_code, 401)
        for user in (self.student, self.faculty):
            self.act_as(user)
            self.assertEqual(self.client.get("/api/admin/students/").status_code, 403)
        self.act_as(self.admin)
        self.assertEqual(self.client.get("/api/admin/students/").json()["data"]["count"], 2)

    def test_search_and_filters(self) -> None:
        self.other.student_profile.city = "Kolkata"
        self.other.student_profile.save()
        self.student.is_active = False
        self.student.save()
        self.act_as(self.admin)

        def emails(url):
            return [item["user"]["email"] for item in self.client.get(url).json()["data"]["results"]]

        self.assertEqual(emails(f"/api/admin/students/?search=ABC-{YEAR}-0001"), ["rahul@gmail.com"])
        self.assertEqual(emails("/api/admin/students/?search=ananya"), ["ananya@gmail.com"])
        self.assertEqual(emails("/api/admin/students/?city=kolkata"), ["ananya@gmail.com"])
        self.assertEqual(emails("/api/admin/students/?is_active=false"), ["rahul@gmail.com"])
        self.assertEqual(self.client.get("/api/admin/students/?gender=X").status_code, 400)

    def test_detail_and_update(self) -> None:
        self.act_as(self.admin)
        url = f"/api/admin/students/{self.student.student_profile.id}/"
        self.assertEqual(self.client.get(url).json()["data"]["profile"]["user"]["email"], "rahul@gmail.com")
        response = self.client.patch(url, {"highest_qualification": "B.Tech", "first_name": "Rahul Kumar"}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["data"]["profile"]["user"]["full_name"], "Rahul Kumar Sen")
        self.assertEqual(self.client.get("/api/admin/students/99999/").status_code, 404)

    def test_manage_students_permission_is_needed_to_edit(self) -> None:
        RolePermission.objects.filter(role=User.Role.ADMIN, permission__name="MANAGE_STUDENTS").delete()
        self.act_as(self.admin)
        url = f"/api/admin/students/{self.student.student_profile.id}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {"city": "Delhi"}, format="json").status_code, 403)

class AdminStudentManagementTests(StudentTestData):
    def test_create_student(self) -> None:
        self.act_as(self.admin)
        data = {"email": "sourav@gmail.com", "first_name": "Sourav", "last_name": "Paul", "password": PASSWORD, "city": "Kolkata"}
        response = self.client.post("/api/admin/students/", data, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        profile = response.json()["data"]["profile"]
        self.assertEqual((profile["student_code"], profile["city"]), (f"ABC-{YEAR}-0003", "Kolkata"))

        response = self.client.post("/api/admin/students/", {**data, "date_of_birth": "2999-01-01"}, format="json")
        self.assertEqual(set(response.json()["errors"]), {"email", "date_of_birth"})

    def test_deactivate_and_activate_student(self) -> None:
        self.act_as(self.admin)
        url = f"/api/admin/students/{self.student.student_profile.id}/"
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)

        response = self.client.patch(url, {"is_active": True}, format="json")
        self.assertEqual(response.json()["data"]["profile"]["user"]["is_active"], True)

    def test_manage_students_permission_is_needed_to_create_or_deactivate(self) -> None:
        RolePermission.objects.filter(role=User.Role.ADMIN, permission__name="MANAGE_STUDENTS").delete()
        self.act_as(self.admin)
        self.assertEqual(self.client.post("/api/admin/students/", {}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/admin/students/{self.student.student_profile.id}/").status_code, 403)