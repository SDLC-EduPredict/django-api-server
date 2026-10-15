from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from accounts.tokens import create_access_token
from attendance.models import Attendance
from courses.models import Course, CourseCategory
from enrolments.models import Enrolment

PASSWORD = "Str0ng-Pass-123!"


class AcademicTestData(TestCase):
    def setUp(self) -> None:
        call_command("seed_permissions", stdout=StringIO())
        self.client = APIClient()
        self.admin = User.objects.create_user("manager@gmail.com", PASSWORD, first_name="Manager", role=User.Role.ADMIN)
        self.faculty = User.objects.create_user("ananya@gmail.com", PASSWORD, first_name="Ananya", role=User.Role.FACULTY)
        self.other_faculty = User.objects.create_user("sourav@gmail.com", PASSWORD, first_name="Sourav", role=User.Role.FACULTY)
        self.student = User.objects.create_user("rahul@gmail.com", PASSWORD, first_name="Rahul", last_name="Sen")
        self.classmate = User.objects.create_user("priya@gmail.com", PASSWORD, first_name="Priya")

        category = CourseCategory.objects.create(name="Programming")
        self.python = self.create_course("Python Programming", category, self.faculty)
        self.django = self.create_course("Django Development", category, self.other_faculty)
        self.draft = self.create_course("Draft Course", category, self.faculty, status=Course.Status.DRAFT)

    def create_course(self, title, category, faculty, status=Course.Status.PUBLISHED):
        return Course.objects.create(
            title=title, category=category, faculty=faculty, short_description=title,
            duration_weeks=8, total_modules=10, status=status)

    def enrol(self, user, course, **extra) -> Enrolment:
        return Enrolment.objects.create(student=user.student_profile, course=course, **extra)

    def act_as(self, user) -> None:
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {create_access_token(user)}")


class EnrolmentModelTests(AcademicTestData):
    def test_dates_are_filled_from_the_course(self) -> None:
        enrolment = self.enrol(self.student, self.python)
        self.assertEqual(enrolment.start_date, timezone.localdate())
        self.assertEqual(enrolment.end_date, timezone.localdate() + timedelta(weeks=8))

    def test_course_start_date_is_used_when_it_is_later(self) -> None:
        self.python.start_date = timezone.localdate() + timedelta(days=10)
        self.python.save()
        enrolment = self.enrol(self.student, self.python)
        self.assertEqual(enrolment.start_date, self.python.start_date)

    def test_course_with_enrolments_cannot_be_deleted(self) -> None:
        self.enrol(self.student, self.python)
        self.act_as(self.admin)
        response = self.client.delete(f"/api/admin/courses/{self.python.id}/")
        self.assertEqual(response.status_code, 400)


class StudentEnrolmentApiTests(AcademicTestData):
    def test_enrol_and_list_my_courses(self) -> None:
        self.act_as(self.student)
        response = self.client.post("/api/student/courses/", {"course": self.python.id}, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        enrolment = response.json()["data"]["enrolment"]
        self.assertEqual((enrolment["status"], enrolment["course"]["title"]), ("ACTIVE", "Python Programming"))
        self.assertEqual(enrolment["progress"]["attendance"]["attendance_percentage"], None)

        courses = self.client.get("/api/student/courses/").json()["data"]["courses"]
        self.assertEqual([course["course"]["title"] for course in courses], ["Python Programming"])

    def test_duplicate_enrolment_is_prevented(self) -> None:
        self.act_as(self.student)
        self.client.post("/api/student/courses/", {"course": self.python.id}, format="json")
        response = self.client.post("/api/student/courses/", {"course": self.python.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"]["course"], ["You are already enrolled in this course."])
        self.assertEqual(Enrolment.objects.count(), 1)

    def test_dropped_student_must_ask_the_admin(self) -> None:
        self.enrol(self.student, self.python, status=Enrolment.Status.DROPPED)
        self.act_as(self.student)
        response = self.client.post("/api/student/courses/", {"course": self.python.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("contact the administrator", response.json()["errors"]["course"][0])

    def test_only_published_courses_can_be_joined(self) -> None:
        self.act_as(self.student)
        for course in (self.draft.id, 99999, "abc"):
            response = self.client.post("/api/student/courses/", {"course": course}, format="json")
            self.assertEqual(response.status_code, 400)

    def test_only_students_can_enrol(self) -> None:
        self.assertEqual(self.client.get("/api/student/courses/").status_code, 401)
        for user in (self.faculty, self.admin):
            self.act_as(user)
            self.assertEqual(self.client.post("/api/student/courses/", {"course": self.python.id}, format="json").status_code, 403)

    def test_student_course_detail_is_private(self) -> None:
        mine = self.enrol(self.student, self.python)
        theirs = self.enrol(self.classmate, self.python)
        self.act_as(self.student)
        self.assertEqual(self.client.get(f"/api/student/courses/{mine.id}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/student/courses/{theirs.id}/").status_code, 404)

    def test_dashboard_counts_enrolments(self) -> None:
        self.enrol(self.student, self.python)
        self.enrol(self.student, self.django, status=Enrolment.Status.COMPLETED)
        self.act_as(self.student)
        summary = self.client.get("/api/student/dashboard/").json()["data"]["summary"]
        self.assertEqual((summary["enrolled_courses"], summary["completed_courses"]), (1, 1))


class StaffEnrolmentApiTests(AcademicTestData):
    def test_faculty_sees_only_own_course_enrolments(self) -> None:
        self.enrol(self.student, self.python)
        self.enrol(self.student, self.django)
        self.act_as(self.faculty)
        results = self.client.get("/api/enrolments/").json()["data"]["results"]
        self.assertEqual([item["course"]["title"] for item in results], ["Python Programming"])

        self.act_as(self.admin)
        self.assertEqual(self.client.get("/api/enrolments/").json()["data"]["count"], 2)
        self.assertEqual(self.client.get("/api/enrolments/?search=django").json()["data"]["count"], 1)
        self.assertEqual(self.client.get("/api/enrolments/?status=XYZ").status_code, 400)

    def test_admin_creates_updates_and_deletes(self) -> None:
        self.act_as(self.admin)
        data = {"student": self.student.student_profile.id, "course": self.python.id, "start_date": "2026-01-05"}
        response = self.client.post("/api/enrolments/", data, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        enrolment_id = response.json()["data"]["enrolment"]["id"]
        self.assertEqual(response.json()["data"]["enrolment"]["end_date"], "2026-03-02")

        duplicate = self.client.post("/api/enrolments/", data, format="json")
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("already enrolled", str(duplicate.json()["errors"]))

        url = f"/api/enrolments/{enrolment_id}/"
        response = self.client.patch(url, {"status": "COMPLETED"}, format="json")
        self.assertEqual(response.json()["data"]["enrolment"]["status"], "COMPLETED")
        self.assertEqual(self.client.patch(url, {"end_date": "2025-01-01"}, format="json").status_code, 400)

        Attendance.objects.create(enrolment_id=enrolment_id, date=date(2026, 1, 6), status=Attendance.Status.PRESENT)
        self.assertEqual(self.client.delete(url).status_code, 400)
        Attendance.objects.all().delete()
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertFalse(Enrolment.objects.exists())

    def test_faculty_cannot_manage_enrolments(self) -> None:
        enrolment = self.enrol(self.student, self.python)
        self.act_as(self.faculty)
        self.assertEqual(self.client.get(f"/api/enrolments/{enrolment.id}/").status_code, 200)
        self.assertEqual(self.client.patch(f"/api/enrolments/{enrolment.id}/", {"status": "DROPPED"}, format="json").status_code, 403)
        data = {"student": self.classmate.student_profile.id, "course": self.python.id}
        self.assertEqual(self.client.post("/api/enrolments/", data, format="json").status_code, 403)

    def test_students_cannot_use_staff_endpoints(self) -> None:
        self.act_as(self.student)
        self.assertEqual(self.client.get("/api/enrolments/").status_code, 403)