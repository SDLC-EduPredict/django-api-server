import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from assignments.models import Assignment, AssignmentSubmission
from enrolments.tests import AcademicTestData

MEDIA_ROOT = tempfile.mkdtemp()
TODAY = timezone.localdate()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AssignmentApiTests(AcademicTestData):
    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.rahul = self.enrol(self.student, self.python)
        self.priya = self.enrol(self.classmate, self.python)
        self.homework = Assignment.objects.create(course=self.python, title="Loops", due_date=TODAY + timedelta(days=3), max_marks=20)
        self.old_homework = Assignment.objects.create(course=self.python, title="Variables", due_date=TODAY - timedelta(days=3), max_marks=10)

    def test_faculty_creates_assignments_only_for_own_courses(self) -> None:
        self.act_as(self.faculty)
        data = {"course": self.python.id, "title": "Functions", "due_date": "2026-12-01"}
        response = self.client.post("/api/assignments/", data, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["data"]["assignment"]["max_marks"], 100)
        self.assertEqual(Assignment.objects.get(title="Functions").created_by, self.faculty)

        response = self.client.post("/api/assignments/", {**data, "course": self.django.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/assignments/").json()["data"]["count"], 3)

        self.act_as(self.other_faculty)
        self.assertEqual(self.client.get(f"/api/assignments/{self.homework.id}/").status_code, 404)

    def test_student_submits_and_resubmits(self) -> None:
        self.act_as(self.student)
        url = f"/api/student/assignments/{self.homework.id}/submit/"
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 400)

        response = self.client.post(url, {"submission_link": "https://github.com/rahul/loops"}, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertFalse(response.json()["data"]["submission"]["is_late"])

        upload = SimpleUploadedFile("loops.py", b"print('hi')", content_type="text/x-python")
        response = self.client.post(url, {"submission_file": upload}, format="multipart")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertIn("/media/assignments/", response.json()["data"]["submission"]["submission_file"])
        self.assertEqual(AssignmentSubmission.objects.count(), 1)

        bad_file = SimpleUploadedFile("virus.exe", b"x", content_type="application/octet-stream")
        self.assertEqual(self.client.post(url, {"submission_file": bad_file}, format="multipart").status_code, 400)

    def test_late_submission_and_other_course(self) -> None:
        self.act_as(self.student)
        response = self.client.post(f"/api/student/assignments/{self.old_homework.id}/submit/", {"submission_text": "done"}, format="json")
        self.assertTrue(response.json()["data"]["submission"]["is_late"])

        other = Assignment.objects.create(course=self.django, title="Models", due_date=TODAY)
        self.assertEqual(self.client.post(f"/api/student/assignments/{other.id}/submit/", {"submission_text": "x"}, format="json").status_code, 404)

    def test_grading_and_average(self) -> None:
        AssignmentSubmission.objects.create(assignment=self.homework, enrolment=self.rahul, submission_text="answer", submitted_at=timezone.now())
        self.act_as(self.faculty)
        url = f"/api/assignments/{self.homework.id}/submissions/"

        students = self.client.get(url).json()["data"]["students"]
        self.assertEqual(sorted(row["status"] for row in students), ["PENDING", "SUBMITTED"])

        too_many = self.client.post(url, {"records": [{"enrolment": self.rahul.id, "marks": 25}]}, format="json")
        self.assertEqual(too_many.status_code, 400)

        records = [{"enrolment": self.rahul.id, "marks": 18, "feedback": "Good"}]
        self.assertEqual(self.client.post(url, {"records": records}, format="json").status_code, 200)
        old_url = f"/api/assignments/{self.old_homework.id}/submissions/"
        self.client.post(old_url, {"records": [{"enrolment": self.rahul.id, "marks": 7}]}, format="json")

        self.act_as(self.student)
        resubmit = self.client.post(f"/api/student/assignments/{self.homework.id}/submit/", {"submission_text": "again"}, format="json")
        self.assertEqual(resubmit.status_code, 400)

        course = self.client.get("/api/student/assignments/").json()["data"]["courses"][0]
        self.assertEqual(course["summary"]["assignment_average"], 80.0)
        self.assertEqual({item["title"]: item["my_status"] for item in course["assignments"]}, {"Loops": "GRADED", "Variables": "GRADED"})

        self.act_as(self.classmate)
        course = self.client.get("/api/student/assignments/?status=OVERDUE").json()["data"]["courses"][0]
        self.assertEqual([item["title"] for item in course["assignments"]], ["Variables"])

    def test_update_and_delete_rules(self) -> None:
        AssignmentSubmission.objects.create(assignment=self.homework, enrolment=self.rahul, marks=15, status="GRADED")
        self.act_as(self.faculty)
        url = f"/api/assignments/{self.homework.id}/"
        self.assertEqual(self.client.patch(url, {"max_marks": 10}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"title": "Loops and lists"}, format="json").json()["data"]["assignment"]["title"], "Loops and lists")
        self.assertEqual(self.client.delete(url).status_code, 400)
        self.assertEqual(self.client.delete(f"/api/assignments/{self.old_homework.id}/").status_code, 200)

    def test_students_cannot_create_or_grade(self) -> None:
        self.act_as(self.student)
        self.assertEqual(self.client.get("/api/assignments/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/assignments/{self.homework.id}/submissions/").status_code, 403)