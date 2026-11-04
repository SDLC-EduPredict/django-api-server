import shutil
import tempfile
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from assessments.models import Assessment, AssessmentResult
from assignments.models import Assignment, AssignmentSubmission
from attendance.models import Attendance
from ml_prediction import services
from performance.tests import TODAY, PerformanceTestData
from permissions.models import Permission, RolePermission

MODEL_DIR = tempfile.mkdtemp()


def tearDownModule():
    shutil.rmtree(MODEL_DIR, ignore_errors=True)


@override_settings(ML_MODEL_DIR=MODEL_DIR)
class AnalyticsTestData(PerformanceTestData):
    def setUp(self) -> None:
        super().setUp()
        services.loaded_models.clear()
        self.build_rahul_example()
        self.add_attendance(self.priya, present=1, absent=4)
        self.sourav = self.enrol(self.classmate, self.django)
        self.add_attendance(self.sourav, present=5, absent=0)

    def give(self, role, permission_name) -> None:
        RolePermission.objects.get_or_create(role=role, permission=Permission.objects.get(name=permission_name))


class AdminDashboardTests(AnalyticsTestData):
    URL = "/api/admin/dashboard/"

    def test_only_admins(self) -> None:
        self.assertEqual(self.client.get(self.URL).status_code, 401)
        for user in (self.student, self.faculty):
            self.act_as(user)
            self.assertEqual(self.client.get(self.URL).status_code, 403)

    def test_dashboard_numbers(self) -> None:
        self.act_as(self.admin)
        data = self.client.get(self.URL).json()["data"]
        summary = data["summary"]
        self.assertEqual((summary["total_students"], summary["total_courses"], summary["active_enrolments"]), (2, 3, 3))
        self.assertEqual(summary["average_attendance"], round((88 + 20 + 100) / 3, 2))
        self.assertEqual(summary["students_needing_attention"], 1)
        self.assertEqual(data["people"]["active_faculty"], 2)
        self.assertEqual(data["courses"]["DRAFT"], 1)
        self.assertEqual(data["enrolments"]["ACTIVE"], 3)
        self.assertEqual(data["performance_indicators"], {"GOOD": 2, "AVERAGE": 0, "NEEDS_ATTENTION": 1, "NO_DATA": 0})
        self.assertEqual(data["students_needing_attention"][0]["student_code"], self.classmate.student_profile.student_code)
        self.assertIn("Attendance is below 75%", data["students_needing_attention"][0]["reasons"])
        self.assertIsNone(data["active_model"])
        self.assertEqual(data["predictions"]["total_predictions"], 0)

    def test_dashboard_with_a_trained_model(self) -> None:
        services.train_model()
        self.act_as(self.admin)
        data = self.client.get(self.URL).json()["data"]
        self.assertEqual(data["active_model"]["name"], "v1")
        self.assertEqual(data["predictions"]["total_predictions"], 1)
        self.assertEqual(sum(band["count"] for band in data["predictions"]["score_bands"]), 1)
        self.assertEqual(len(data["latest_predictions"]), 1)


class FacultyDashboardTests(AnalyticsTestData):
    URL = "/api/faculty/dashboard/"

    def test_only_faculty(self) -> None:
        for user in (self.student, self.admin):
            self.act_as(user)
            self.assertEqual(self.client.get(self.URL).status_code, 403)

    def test_dashboard_shows_only_own_courses(self) -> None:
        homework = Assignment.objects.create(course=self.python, title="Functions", due_date=TODAY + timedelta(days=3))
        AssignmentSubmission.objects.create(assignment=homework, enrolment=self.priya, submission_text="done", submitted_at=timezone.now())
        Assessment.objects.create(course=self.python, title="Exam", assessment_type="EXAM", assessment_date=TODAY + timedelta(days=7))
        Assessment.objects.create(course=self.django, title="Other", assessment_date=TODAY + timedelta(days=7))

        self.act_as(self.faculty)
        data = self.client.get(self.URL).json()["data"]
        self.assertEqual((data["summary"]["total_students"], data["summary"]["total_courses"]), (2, 2))
        self.assertEqual(data["work"]["submissions_to_grade"], 1)
        self.assertEqual(data["work"]["upcoming_assessments"], 2)
        self.assertEqual(data["work"]["assignments_due_soon"], 2)
        python = next(course for course in data["courses"] if course["title"] == "Python Programming")
        self.assertEqual((python["students"], python["good"], python["needs_attention"], python["low_attendance_students"]), (2, 1, 1, 1))
        self.assertEqual(python["average_attendance"], 54.0)
        self.assertEqual([row["course"] for row in data["students_needing_attention"]], ["Python Programming"])

        self.act_as(self.other_faculty)
        data = self.client.get(self.URL).json()["data"]
        self.assertEqual(data["summary"]["total_students"], 1)
        self.assertEqual(data["students_needing_attention"], [])


class MyStudentsTests(AnalyticsTestData):
    def test_faculty_sees_own_students_with_filters(self) -> None:
        self.act_as(self.faculty)
        body = self.client.get("/api/faculty/students/").json()["data"]
        self.assertEqual(body["count"], 2)
        rows = self.client.get("/api/faculty/students/?indicator=NEEDS_ATTENTION").json()["data"]["results"]
        self.assertEqual([row["student_name"] for row in rows], ["Priya"])
        self.assertEqual(self.client.get("/api/faculty/students/?indicator=BAD").status_code, 400)

        self.act_as(self.admin)
        self.assertEqual(self.client.get("/api/faculty/students/").json()["data"]["count"], 3)

    def test_student_report(self) -> None:
        url = f"/api/faculty/students/{self.classmate.student_profile.id}/"
        self.act_as(self.other_faculty)
        data = self.client.get(url).json()["data"]
        self.assertEqual([course["course"]["title"] for course in data["courses"]], ["Django Development"])

        self.act_as(self.admin)
        data = self.client.get(url).json()["data"]
        self.assertEqual(len(data["courses"]), 2)
        self.assertEqual(data["overall"]["courses"], 2)
        self.assertEqual(data["courses"][0]["prediction"], None)

        self.act_as(self.other_faculty)
        self.assertEqual(self.client.get(f"/api/faculty/students/{self.student.student_profile.id}/").status_code, 404)
        self.assertEqual(self.client.get("/api/faculty/students/99999/").status_code, 404)


class ReportTests(AnalyticsTestData):
    def test_faculty_needs_view_reports(self) -> None:
        self.act_as(self.faculty)
        self.assertEqual(self.client.get("/api/reports/overview/").status_code, 403)
        self.give("FACULTY", "VIEW_REPORTS")
        overview = self.client.get("/api/reports/overview/").json()["data"]["overview"]
        self.assertEqual(overview["total_courses"], 2)

    def test_course_performance_report_and_csv(self) -> None:
        self.act_as(self.admin)
        courses = self.client.get("/api/reports/course-performance/?status=PUBLISHED").json()["data"]["courses"]
        self.assertEqual([course["title"] for course in courses], ["Django Development", "Python Programming"])
        self.assertEqual(courses[0]["average_attendance"], 100.0)
        self.assertEqual(self.client.get("/api/reports/course-performance/?status=X").status_code, 400)

        response = self.client.get("/api/reports/course-performance/?export=csv")
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("average_attendance", response.content.decode().splitlines()[0])

        RolePermission.objects.filter(role="ADMIN", permission__name="EXPORT_REPORTS").delete()
        self.assertEqual(self.client.get("/api/reports/course-performance/?export=csv").status_code, 403)

    def test_students_needing_attention_report(self) -> None:
        self.act_as(self.admin)
        body = self.client.get("/api/reports/students-needing-attention/").json()["data"]
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["indicator"], "NEEDS_ATTENTION")
        self.assertEqual(self.client.get(f"/api/reports/students-needing-attention/?course={self.django.id}").json()["data"]["count"], 0)

        lines = self.client.get("/api/reports/students-needing-attention/?export=csv").content.decode().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("Attendance is below 75%; Overall score is below 60", lines[1])

    def test_prediction_distribution(self) -> None:
        self.act_as(self.admin)
        data = self.client.get("/api/reports/prediction-distribution/").json()["data"]
        self.assertEqual((data["total_predictions"], data["active_model"]), (0, None))

        services.train_model()
        Attendance.objects.create(enrolment=self.priya, date=TODAY, status="PRESENT")
        mock = Assessment.objects.get(title="Mock Test 1")
        AssessmentResult.objects.create(assessment=mock, enrolment=self.priya, marks_obtained=30)
        loops = Assignment.objects.get(title="Loops")
        AssignmentSubmission.objects.create(assignment=loops, enrolment=self.priya, status="GRADED", marks=40)
        data = self.client.get("/api/reports/prediction-distribution/").json()["data"]
        self.assertEqual(data["total_predictions"], 2)
        self.assertEqual(sum(data["indicators"].values()), 2)
        self.assertEqual(self.client.get(f"/api/reports/prediction-distribution/?course={self.django.id}").json()["data"]["total_predictions"], 0)