import shutil
import tempfile
from io import BytesIO, StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from accounts.tokens import create_access_token
from courses.models import Course, CourseCategory
from permissions.models import RolePermission

PASSWORD = "Str0ng-Pass-123!"
MEDIA_ROOT = tempfile.mkdtemp()


def image_file(name="photo.png"):
    buffer = BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class CourseTestData(TestCase):
    def setUp(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        self.client = APIClient()
        self.admin = User.objects.create_user("manager@gmail.com", PASSWORD, first_name="Manager", role=User.Role.ADMIN)
        self.student = User.objects.create_user("rahul@gmail.com", PASSWORD, first_name="Rahul")
        self.faculty = User.objects.create_user("ananya@gmail.com", PASSWORD, first_name="Ananya", last_name="Roy", role=User.Role.FACULTY)
        self.faculty.faculty_profile.designation = "Python Trainer"
        self.faculty.faculty_profile.save()

        self.programming = CourseCategory.objects.create(name="Programming")
        self.data_science = CourseCategory.objects.create(name="Data Science")
        self.hidden_category = CourseCategory.objects.create(name="Old Courses", is_active=False)

        self.python = self.create_course("Python Programming", self.programming, fee=8000, faculty=self.faculty)
        self.django = self.create_course("Django Development", self.programming, fee=12000, level=Course.Level.INTERMEDIATE)
        self.ml = self.create_course("Machine Learning", self.data_science, fee=18000, level=Course.Level.ADVANCED, mode=Course.Mode.ONLINE)
        self.draft = self.create_course("Draft Course", self.programming, status=Course.Status.DRAFT)
        self.old = self.create_course("Old Course", self.hidden_category)

    def create_course(self, title, category, status=Course.Status.PUBLISHED, **extra):
        values = {"short_description": f"{title} course", "duration_weeks": 8, "total_modules": 10, **extra}
        return Course.objects.create(title=title, category=category, status=status, **values)

    def act_as(self, user) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_access_token(user)}")

    def course_data(self, **changes) -> dict:
        data = {
            "category": self.programming.id, "faculty": str(self.faculty.id), "title": "Full Stack Development",
            "short_description": "React and Django", "description": "Long text", "level": "ADVANCED", "mode": "HYBRID",
            "duration_weeks": 24, "total_modules": 20, "fee": "30000.00", "status": "PUBLISHED",
        }
        return {**data, **changes}


class CourseModelTests(CourseTestData):
    def test_slug_is_made_from_the_title_and_is_unique(self) -> None:
        self.assertEqual(self.python.slug, "python-programming")
        again = self.create_course("Python Programming", self.programming)
        self.assertEqual(again.slug, "python-programming-2")
        self.assertEqual(self.programming.slug, "programming")

    def test_seed_courses_is_repeatable(self) -> None:
        call_command("seed_courses", stdout=StringIO())
        count = Course.objects.count()
        call_command("seed_courses", stdout=StringIO())
        self.assertEqual(Course.objects.count(), count)
        self.assertTrue(Course.objects.filter(slug="artificial-intelligence", status=Course.Status.PUBLISHED).exists())


class PublicCourseApiTests(CourseTestData):
    def titles(self, url) -> list[str]:
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.json())
        return [course["title"] for course in response.json()["data"]["results"]]

    def test_categories_show_only_active_ones_with_published_course_count(self) -> None:
        response = self.client.get("/api/categories/")
        self.assertEqual(response.status_code, 200)
        categories = {item["name"]: item["course_count"] for item in response.json()["data"]["categories"]}
        self.assertEqual(categories, {"Data Science": 1, "Programming": 2})

    def test_course_list_shows_only_published_courses_of_active_categories(self) -> None:
        self.assertEqual(sorted(self.titles("/api/courses/")), ["Django Development", "Machine Learning", "Python Programming"])

    def test_response_format_and_trainer_information(self) -> None:
        body = self.client.get("/api/courses/?search=python").json()
        self.assertEqual((body["status"], body["errors"]), ("success", None))
        course = body["data"]["results"][0]
        self.assertEqual(course["category"]["slug"], "programming")
        self.assertEqual(course["faculty"]["full_name"], "Ananya Roy")
        self.assertEqual(course["faculty"]["designation"], "Python Trainer")
        self.assertNotIn("email", course["faculty"])
        self.assertEqual(course["fee"], 8000)

    def test_search(self) -> None:
        self.assertEqual(self.titles("/api/courses/?search=machine"), ["Machine Learning"])
        self.assertEqual(self.titles("/api/courses/?search=django development"), ["Django Development"])
        self.assertEqual(self.titles("/api/courses/?search=ananya"), ["Python Programming"])
        self.assertEqual(self.titles("/api/courses/?search=draft"), [])

    def test_filters(self) -> None:
        self.assertEqual(self.titles(f"/api/courses/?category={self.data_science.id}"), ["Machine Learning"])
        self.assertEqual(self.titles("/api/courses/?category=data-science"), ["Machine Learning"])
        self.assertEqual(self.titles("/api/courses/?level=INTERMEDIATE"), ["Django Development"])
        self.assertEqual(self.titles("/api/courses/?mode=ONLINE"), ["Machine Learning"])
        self.assertEqual(self.titles(f"/api/courses/?faculty={self.faculty.id}"), ["Python Programming"])
        self.assertEqual(self.titles("/api/courses/?min_fee=10000&max_fee=15000"), ["Django Development"])
        self.assertEqual(self.titles("/api/courses/?ordering=fee"), ["Python Programming", "Django Development", "Machine Learning"])
        self.assertEqual(self.titles("/api/courses/?status=DRAFT"), [])

    def test_bad_filters_return_400(self) -> None:
        response = self.client.get("/api/courses/?level=EXPERT&min_fee=abc&faculty=123&ordering=hack")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()["errors"]), {"level", "min_fee", "faculty", "ordering"})
        response = self.client.get("/api/courses/?min_fee=500&max_fee=100")
        self.assertIn("max_fee", response.json()["errors"])

    def test_pagination(self) -> None:
        body = self.client.get("/api/courses/?page_size=2").json()["data"]
        self.assertEqual((body["count"], len(body["results"])), (3, 2))
        self.assertIsNotNone(body["next"])
        self.assertEqual(self.client.get("/api/courses/?page=99").status_code, 404)

    def test_course_detail_by_id_and_slug(self) -> None:
        by_id = self.client.get(f"/api/courses/{self.python.id}/")
        self.assertEqual(by_id.status_code, 200)
        self.assertEqual(by_id.json()["data"]["course"]["description"], "")
        by_slug = self.client.get("/api/courses/python-programming/")
        self.assertEqual(by_slug.json()["data"]["course"]["id"], self.python.id)

    def test_draft_and_hidden_courses_are_not_found(self) -> None:
        for course in (self.draft, self.old):
            self.assertEqual(self.client.get(f"/api/courses/{course.id}/").status_code, 404)
        self.assertEqual(self.client.get("/api/courses/no-such-course/").status_code, 404)

    def test_faculty_list_and_detail(self) -> None:
        body = self.client.get("/api/faculty/").json()["data"]
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["course_count"], 1)
        self.assertNotIn("email", body["results"][0])

        detail = self.client.get(f"/api/faculty/{self.faculty.id}/").json()["data"]
        self.assertEqual([course["title"] for course in detail["courses"]], ["Python Programming"])
        self.assertEqual(self.client.get(f"/api/faculty/{self.student.id}/").status_code, 404)

    def test_inactive_faculty_is_hidden(self) -> None:
        self.faculty.is_active = False
        self.faculty.save()
        self.assertEqual(self.client.get("/api/faculty/").json()["data"]["count"], 0)


class AdminCategoryApiTests(CourseTestData):
    def test_login_and_permission_are_required(self) -> None:
        self.assertEqual(self.client.get("/api/admin/categories/").status_code, 401)
        self.act_as(self.student)
        self.assertEqual(self.client.post("/api/admin/categories/", {"name": "Design"}, format="json").status_code, 403)
        self.act_as(self.faculty)
        self.assertEqual(self.client.get("/api/admin/categories/").status_code, 403)

    def test_admin_sees_every_category(self) -> None:
        self.act_as(self.admin)
        categories = self.client.get("/api/admin/categories/").json()["data"]["categories"]
        self.assertEqual({item["name"]: item["course_count"] for item in categories}, {"Data Science": 1, "Old Courses": 1, "Programming": 3})

    def test_create_update_delete(self) -> None:
        self.act_as(self.admin)
        response = self.client.post("/api/admin/categories/", {"name": "Cloud Computing"}, format="json")
        self.assertEqual(response.status_code, 201)
        category = response.json()["data"]["category"]
        self.assertEqual((category["slug"], category["course_count"]), ("cloud-computing", 0))

        url = f"/api/admin/categories/{category['id']}/"
        response = self.client.patch(url, {"is_active": False}, format="json")
        self.assertEqual(response.json()["data"]["category"]["name"], "Cloud Computing")
        self.assertFalse(response.json()["data"]["category"]["is_active"])

        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_duplicate_name_is_rejected_ignoring_case(self) -> None:
        self.act_as(self.admin)
        response = self.client.post("/api/admin/categories/", {"name": "programming"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["errors"])

    def test_category_with_courses_cannot_be_deleted(self) -> None:
        self.act_as(self.admin)
        response = self.client.delete(f"/api/admin/categories/{self.programming.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(CourseCategory.objects.filter(pk=self.programming.pk).exists())


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AdminCourseApiTests(CourseTestData):
    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_login_and_permission_are_required(self) -> None:
        self.assertEqual(self.client.post("/api/admin/courses/", self.course_data(), format="json").status_code, 401)
        for user in (self.student, self.faculty):
            self.act_as(user)
            self.assertEqual(self.client.post("/api/admin/courses/", self.course_data(), format="json").status_code, 403)
            self.assertEqual(self.client.delete(f"/api/admin/courses/{self.python.id}/").status_code, 403)
        self.assertEqual(Course.objects.count(), 5)

    def test_admin_list_includes_drafts_and_filters_by_status(self) -> None:
        self.act_as(self.admin)
        self.assertEqual(self.client.get("/api/admin/courses/").json()["data"]["count"], 5)
        drafts = self.client.get("/api/admin/courses/?status=DRAFT").json()["data"]["results"]
        self.assertEqual([course["title"] for course in drafts], ["Draft Course"])

    def test_create_course(self) -> None:
        self.act_as(self.admin)
        response = self.client.post("/api/admin/courses/", self.course_data(), format="json")
        self.assertEqual(response.status_code, 201, response.json())
        course = response.json()["data"]["course"]
        self.assertEqual((course["slug"], course["faculty"]["full_name"], course["fee"]), ("full-stack-development", "Ananya Roy", 30000))
        self.assertEqual(self.client.get(f"/api/courses/{course['id']}/").status_code, 200)

    def test_create_course_uses_defaults_for_level_mode_status_and_fee(self) -> None:
        self.act_as(self.admin)
        data = {"category": self.programming.id, "title": "React JS", "short_description": "React", "duration_weeks": 6, "total_modules": 8}
        response = self.client.post("/api/admin/courses/", data, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        course = response.json()["data"]["course"]
        self.assertEqual((course["level"], course["mode"], course["status"], course["fee"]), ("BEGINNER", "OFFLINE", "DRAFT", 0))

    def test_create_course_with_thumbnail(self) -> None:
        self.act_as(self.admin)
        response = self.client.post("/api/admin/courses/", self.course_data(thumbnail=image_file()), format="multipart")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertTrue(response.json()["data"]["course"]["thumbnail"].startswith("http://testserver/media/courses/"))

    def test_create_course_validation(self) -> None:
        self.act_as(self.admin)
        response = self.client.post("/api/admin/courses/", {"title": ""}, format="json")
        self.assertEqual(response.status_code, 400)
        for field in ("category", "title", "short_description", "duration_weeks", "total_modules"):
            self.assertIn(field, response.json()["errors"])

        bad = self.course_data(fee="-5", duration_weeks=0, level="EXPERT", status="LIVE", slug="python-programming", faculty=str(self.student.id))
        errors = self.client.post("/api/admin/courses/", bad, format="json").json()["errors"]
        self.assertEqual(set(errors), {"fee", "duration_weeks", "level", "status", "slug", "faculty"})

    def test_inactive_faculty_cannot_be_assigned(self) -> None:
        self.faculty.is_active = False
        self.faculty.save()
        self.act_as(self.admin)
        response = self.client.post("/api/admin/courses/", self.course_data(), format="json")
        self.assertIn("faculty", response.json()["errors"])

    def test_patch_changes_only_sent_fields(self) -> None:
        self.act_as(self.admin)
        response = self.client.patch(f"/api/admin/courses/{self.draft.id}/", {"status": "PUBLISHED", "fee": 999}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        course = response.json()["data"]["course"]
        self.assertEqual((course["status"], course["fee"], course["title"]), ("PUBLISHED", 999, "Draft Course"))
        self.assertEqual(self.client.get(f"/api/courses/{self.draft.id}/").status_code, 200)

    def test_patch_can_remove_the_faculty(self) -> None:
        self.act_as(self.admin)
        response = self.client.patch(f"/api/admin/courses/{self.python.id}/", {"faculty": None}, format="json")
        self.assertIsNone(response.json()["data"]["course"]["faculty"])

    def test_delete_course(self) -> None:
        self.act_as(self.admin)
        self.assertEqual(self.client.delete(f"/api/admin/courses/{self.python.id}/").status_code, 200)
        self.assertFalse(Course.objects.filter(pk=self.python.pk).exists())
        self.assertEqual(self.client.get(f"/api/admin/courses/{self.python.id}/").status_code, 404)

    def test_permissions_come_from_the_role_permission_table(self) -> None:
        RolePermission.objects.filter(role=User.Role.ADMIN, permission__name="DELETE_COURSE").delete()
        self.act_as(self.admin)
        response = self.client.delete(f"/api/admin/courses/{self.python.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["errors"]["required_permission"], "DELETE_COURSE")
        self.assertEqual(self.client.patch(f"/api/admin/courses/{self.python.id}/", {"fee": 1}, format="json").status_code, 200)