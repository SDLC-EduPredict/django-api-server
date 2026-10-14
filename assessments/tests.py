from datetime import timedelta

from django.utils import timezone

from assessments.models import Assessment, AssessmentResult
from enrolments.tests import AcademicTestData

TODAY = timezone.localdate()


class AssessmentApiTests(AcademicTestData):
    def setUp(self) -> None:
        super().setUp()
        self.rahul = self.enrol(self.student, self.python)
        self.priya = self.enrol(self.classmate, self.python)
        self.mock = Assessment.objects.create(course=self.python, title="Mock Test 1", assessment_date=TODAY - timedelta(days=5), max_marks=50, pass_marks=20)
        self.exam = Assessment.objects.create(course=self.python, title="Final Exam", assessment_type="EXAM", assessment_date=TODAY - timedelta(days=1))

    def test_faculty_creates_mock_tests_and_exams(self) -> None:
        self.act_as(self.faculty)
        data = {"course": self.python.id, "title": "Mock Test 2", "assessment_date": "2026-12-10"}
        response = self.client.post("/api/assessments/", data, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        created = response.json()["data"]["assessment"]
        self.assertEqual((created["assessment_type"], created["max_marks"], created["pass_marks"]), ("MOCK_TEST", 100, 40))

        bad = self.client.post("/api/assessments/", {**data, "max_marks": 30, "pass_marks": 40}, format="json")
        self.assertIn("pass_marks", bad.json()["errors"])
        self.assertEqual(self.client.post("/api/assessments/", {**data, "course": self.django.id}, format="json").status_code, 400)
        self.assertEqual(self.client.get("/api/assessments/?assessment_type=EXAM").json()["data"]["count"], 1)

    def test_enter_marks_and_results(self) -> None:
        self.act_as(self.faculty)
        url = f"/api/assessments/{self.mock.id}/results/"
        records = [{"enrolment": self.rahul.id, "marks_obtained": 39}, {"enrolment": self.priya.id, "marks_obtained": 12, "remarks": "Needs practice"}]
        response = self.client.post(url, {"records": records}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        results = {item["student"]["full_name"]: item for item in response.json()["data"]["results"]}
        self.assertEqual((results["Rahul Sen"]["percentage"], results["Rahul Sen"]["result"]), (78.0, "PASS"))
        self.assertEqual(results["Priya"]["result"], "FAIL")

        self.client.post(url, {"records": [{"enrolment": self.rahul.id, "marks_obtained": 40}]}, format="json")
        self.assertEqual(AssessmentResult.objects.get(enrolment=self.rahul).marks_obtained, 40)
        self.assertEqual(AssessmentResult.objects.count(), 2)

        self.assertEqual(self.client.post(url, {"records": [{"enrolment": self.rahul.id, "marks_obtained": 51}]}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"records": [{"enrolment": self.rahul.id, "marks_obtained": -1}]}, format="json").status_code, 400)
        self.assertEqual(len(self.client.get(url).json()["data"]["students"]), 2)

    def test_marks_cannot_be_entered_before_the_assessment(self) -> None:
        future = Assessment.objects.create(course=self.python, title="Next week", assessment_date=TODAY + timedelta(days=7))
        self.act_as(self.faculty)
        response = self.client.post(f"/api/assessments/{future.id}/results/", {"records": [{"enrolment": self.rahul.id, "marks_obtained": 10}]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_student_results_and_averages(self) -> None:
        AssessmentResult.objects.create(assessment=self.mock, enrolment=self.rahul, marks_obtained=39)
        AssessmentResult.objects.create(assessment=self.exam, enrolment=self.rahul, marks_obtained=82)
        AssessmentResult.objects.create(assessment=self.mock, enrolment=self.priya, marks_obtained=10)

        self.act_as(self.student)
        course = self.client.get("/api/student/results/").json()["data"]["courses"][0]
        self.assertEqual(course["summary"]["mock_test_average"], 78.0)
        self.assertEqual(course["summary"]["exam_average"], 82.0)
        self.assertEqual(course["summary"]["assessment_average"], 80.0)
        self.assertEqual(course["summary"]["passed"], 2)

        exams = self.client.get("/api/student/results/?assessment_type=EXAM").json()["data"]["courses"][0]["assessments"]
        self.assertEqual([(item["title"], item["my_result"]["marks_obtained"]) for item in exams], [("Final Exam", 82.0)])

    def test_update_delete_rules(self) -> None:
        result = AssessmentResult.objects.create(assessment=self.mock, enrolment=self.rahul, marks_obtained=45)
        self.act_as(self.faculty)
        url = f"/api/assessments/{self.mock.id}/"
        self.assertEqual(self.client.patch(url, {"max_marks": 40, "pass_marks": 20}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, 400)

        self.act_as(self.other_faculty)
        self.assertEqual(self.client.delete(f"/api/assessments/results/{result.id}/").status_code, 404)
        self.act_as(self.faculty)
        self.assertEqual(self.client.delete(f"/api/assessments/results/{result.id}/").status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 200)

    def test_students_cannot_manage_assessments(self) -> None:
        self.act_as(self.student)
        self.assertEqual(self.client.get("/api/assessments/").status_code, 403)
        self.assertEqual(self.client.post(f"/api/assessments/{self.mock.id}/results/", {"records": []}, format="json").status_code, 403)
