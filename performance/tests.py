from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from assessments.models import Assessment, AssessmentResult
from assignments.models import Assignment, AssignmentSubmission
from attendance.models import Attendance
from enrolments.tests import AcademicTestData
from performance.models import Performance
from performance.signals import create_missing_performances
from performance.utils import performance_indicator

TODAY = timezone.localdate()


class PerformanceTestData(AcademicTestData):
    def setUp(self) -> None:
        super().setUp()
        self.rahul = self.enrol(self.student, self.python)
        self.priya = self.enrol(self.classmate, self.python)

    def add_attendance(self, enrolment, present, absent) -> None:
        statuses = ["PRESENT"] * present + ["ABSENT"] * absent
        for days, status in enumerate(statuses, start=1):
            Attendance.objects.create(enrolment=enrolment, date=TODAY - timedelta(days=days), status=status)

    def build_rahul_example(self) -> None:
        self.add_attendance(self.rahul, present=22, absent=3)
        assignment = Assignment.objects.create(course=self.python, title="Loops", due_date=TODAY)
        AssignmentSubmission.objects.create(assignment=assignment, enrolment=self.rahul, status="GRADED", marks=84)
        self.mock = Assessment.objects.create(course=self.python, title="Mock Test 1", assessment_date=TODAY)
        AssessmentResult.objects.create(assessment=self.mock, enrolment=self.rahul, marks_obtained=78)

    def performance_of(self, enrolment) -> Performance:
        return Performance.objects.get(enrolment=enrolment)


class PerformanceCalculationTests(PerformanceTestData):
    def test_enrolment_gets_an_empty_performance(self) -> None:
        performance = self.performance_of(self.rahul)
        self.assertEqual(performance.indicator, "NO_DATA")
        self.assertIsNone(performance.overall_score)

    def test_records_update_the_performance(self) -> None:
        self.build_rahul_example()
        performance = self.performance_of(self.rahul)
        self.assertEqual(float(performance.attendance_percentage), 88.0)
        self.assertEqual(float(performance.assignment_average), 84.0)
        self.assertEqual(float(performance.mock_test_average), 78.0)
        self.assertEqual(float(performance.overall_score), 83.33)
        self.assertEqual(performance.indicator, "GOOD")

    def test_deleting_a_record_updates_the_performance(self) -> None:
        self.build_rahul_example()
        AssessmentResult.objects.filter(enrolment=self.rahul).delete()
        self.assertIsNone(self.performance_of(self.rahul).mock_test_average)

    def test_changing_max_marks_updates_the_performance(self) -> None:
        self.build_rahul_example()
        self.mock.max_marks = 80
        self.mock.save()
        self.assertEqual(float(self.performance_of(self.rahul).mock_test_average), 97.5)

    def test_exam_is_kept_apart_from_mock_tests(self) -> None:
        self.build_rahul_example()
        exam = Assessment.objects.create(course=self.python, title="Final Exam", assessment_type="EXAM", assessment_date=TODAY)
        AssessmentResult.objects.create(assessment=exam, enrolment=self.rahul, marks_obtained=90)
        performance = self.performance_of(self.rahul)
        self.assertEqual((float(performance.mock_test_average), float(performance.exam_average), float(performance.assessment_average)), (78.0, 90.0, 84.0))

    def test_deleting_a_student_with_records_works(self) -> None:
        self.build_rahul_example()
        self.student.delete()
        connection.check_constraints()
        self.assertFalse(Performance.objects.filter(enrolment_id=self.rahul.id).exists())

    def test_missing_performances_are_created(self) -> None:
        self.build_rahul_example()
        Performance.objects.all().delete()
        create_missing_performances(sender=None)
        self.assertEqual(self.performance_of(self.rahul).indicator, "GOOD")
        call_command("refresh_performance", stdout=StringIO())
        self.assertEqual(Performance.objects.count(), 2)

    def test_indicator_thresholds(self) -> None:
        self.assertEqual(performance_indicator(83.7), "GOOD")
        self.assertEqual(performance_indicator(72.4), "AVERAGE")
        self.assertEqual(performance_indicator(58.6), "NEEDS_ATTENTION")
        self.assertEqual(performance_indicator(None), "NO_DATA")


class StaffPerformanceApiTests(PerformanceTestData):
    def test_faculty_enters_manual_inputs(self) -> None:
        self.build_rahul_example()
        performance = self.performance_of(self.rahul)
        self.act_as(self.faculty)
        url = f"/api/performance/{performance.id}/"

        data = {"practice_hours": 10, "previous_score": 80, "modules_completed": 9, "participation": "HIGH"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        body = response.json()["data"]["performance"]
        self.assertEqual((body["modules_completed_percentage"], body["overall_score"], body["participation_score"]), (90.0, 85.0, 3))
        self.assertEqual(body["updated_by"], "Ananya")

        response = self.client.patch(url, {"practice_hours": 12}, format="json")
        self.assertEqual(response.json()["data"]["performance"]["previous_score"], 80.0)

    def test_invalid_inputs_are_rejected(self) -> None:
        url = f"/api/performance/{self.performance_of(self.rahul).id}/"
        self.act_as(self.faculty)
        response = self.client.patch(url, {"modules_completed": 11, "previous_score": 120, "participation": "SUPER", "practice_hours": -1}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()["errors"]), {"modules_completed", "previous_score", "participation", "practice_hours"})

    def test_faculty_sees_only_own_courses(self) -> None:
        other = self.enrol(self.classmate, self.django)
        self.act_as(self.faculty)
        self.assertEqual(self.client.get(f"/api/performance/{self.performance_of(other).id}/").status_code, 404)
        self.assertEqual(self.client.get("/api/performance/").json()["data"]["count"], 2)
        self.act_as(self.admin)
        self.assertEqual(self.client.get("/api/performance/").json()["data"]["count"], 3)

    def test_list_filters_and_ordering(self) -> None:
        self.build_rahul_example()
        self.act_as(self.faculty)
        rows = self.client.get("/api/performance/?indicator=GOOD").json()["data"]["results"]
        self.assertEqual([row["student"]["full_name"] for row in rows], ["Rahul Sen"])
        rows = self.client.get("/api/performance/?ordering=-overall_score").json()["data"]["results"]
        self.assertEqual([row["indicator"] for row in rows], ["GOOD", "NO_DATA"])
        self.assertEqual(self.client.get("/api/performance/?indicator=BAD").status_code, 400)

    def test_course_summary(self) -> None:
        self.build_rahul_example()
        self.act_as(self.faculty)
        response = self.client.get(f"/api/performance/summary/?course={self.python.id}")
        self.assertEqual(response.status_code, 200, response.json())
        summary = response.json()["data"]["summary"]
        self.assertEqual((summary["students"], summary["indicators"]["GOOD"], summary["indicators"]["NO_DATA"]), (2, 1, 1))
        self.assertEqual(self.client.get(f"/api/performance/summary/?course={self.django.id}").status_code, 400)

    def test_student_cannot_use_staff_endpoints(self) -> None:
        self.act_as(self.student)
        self.assertEqual(self.client.get("/api/performance/").status_code, 403)
        self.assertEqual(self.client.patch(f"/api/performance/{self.performance_of(self.rahul).id}/", {}, format="json").status_code, 403)

    def test_ml_dataset(self) -> None:
        self.build_rahul_example()
        self.act_as(self.faculty)
        self.assertEqual(self.client.get("/api/performance/dataset/").status_code, 403)

        self.act_as(self.admin)
        data = self.client.get("/api/performance/dataset/").json()["data"]
        self.assertEqual((data["count"], data["target"]), (2, "final_score"))
        row = data["rows"][0]
        self.assertEqual((row["attendance"], row["assignment_average"], row["mock_test_average"], row["final_score"]), (88.0, 84.0, 78.0, None))

        response = self.client.get("/api/performance/dataset/?export=csv")
        self.assertEqual(response["Content-Type"], "text/csv")
        lines = response.content.decode().splitlines()
        self.assertTrue(lines[0].startswith("enrolment_id,student_code,course,attendance"))
        self.assertEqual(len(lines), 3)


class StudentPerformanceApiTests(PerformanceTestData):
    def test_student_sees_own_performance(self) -> None:
        self.build_rahul_example()
        self.act_as(self.student)
        response = self.client.get("/api/student/performance/")
        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()["data"]
        self.assertEqual((data["overall"]["courses"], data["overall"]["indicator"], data["overall"]["indicator_display"]), (1, "GOOD", "Good"))
        self.assertEqual(data["courses"][0]["performance"]["attendance_percentage"], 88.0)

        dashboard = self.client.get("/api/student/dashboard/").json()["data"]
        self.assertEqual(dashboard["performance"]["indicator"], "GOOD")

    def test_dropped_course_is_hidden(self) -> None:
        self.rahul.status = "DROPPED"
        self.rahul.save()
        self.act_as(self.student)
        data = self.client.get("/api/student/performance/").json()["data"]
        self.assertEqual((data["overall"]["courses"], data["overall"]["indicator"]), (0, "NO_DATA"))

    def test_staff_cannot_use_student_endpoint(self) -> None:
        self.act_as(self.faculty)
        self.assertEqual(self.client.get("/api/student/performance/").status_code, 403)