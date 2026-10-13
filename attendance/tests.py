from datetime import date, timedelta

from django.utils import timezone

from attendance.models import Attendance
from enrolments.models import Enrolment
from enrolments.tests import AcademicTestData


class AttendanceApiTests(AcademicTestData):
    def setUp(self) -> None:
        super().setUp()
        self.rahul = self.enrol(self.student, self.python)
        self.priya = self.enrol(self.classmate, self.python)
        self.other_course = self.enrol(self.student, self.django)

    def record(self, day, records):
        return self.client.post("/api/attendance/", {"date": day, "records": records}, format="json")

    def test_record_attendance_for_a_class(self) -> None:
        self.act_as(self.faculty)
        response = self.record("2026-10-01", [
            {"enrolment": self.rahul.id, "status": "PRESENT"},
            {"enrolment": self.priya.id, "status": "ABSENT", "remarks": "Sick"},
        ])
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(Attendance.objects.count(), 2)
        self.assertEqual(Attendance.objects.get(enrolment=self.rahul).marked_by, self.faculty)

    def test_recording_the_same_day_again_updates_it(self) -> None:
        self.act_as(self.faculty)
        self.record("2026-10-01", [{"enrolment": self.rahul.id, "status": "ABSENT"}])
        self.record("2026-10-01", [{"enrolment": self.rahul.id, "status": "LATE"}])
        self.assertEqual(Attendance.objects.get().status, "LATE")

    def test_validation(self) -> None:
        self.act_as(self.faculty)
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertIn("date", self.record(tomorrow, [{"enrolment": self.rahul.id, "status": "PRESENT"}]).json()["errors"])
        self.assertIn("records", self.record("2026-10-01", []).json()["errors"])
        errors = self.record("2026-10-01", [{"enrolment": self.rahul.id, "status": "SLEEPING"}, {"enrolment": self.other_course.id, "status": "PRESENT"}]).json()["errors"]
        self.assertEqual(set(errors), {"0", "1"})
        same_twice = [{"enrolment": self.rahul.id, "status": "PRESENT"}, {"enrolment": self.rahul.id, "status": "ABSENT"}]
        self.assertIn("records", self.record("2026-10-01", same_twice).json()["errors"])
        self.assertFalse(Attendance.objects.exists())

    def test_dropped_enrolment_cannot_get_attendance(self) -> None:
        self.priya.status = Enrolment.Status.DROPPED
        self.priya.save()
        self.act_as(self.faculty)
        self.assertEqual(self.record("2026-10-01", [{"enrolment": self.priya.id, "status": "PRESENT"}]).status_code, 400)

    def test_percentage_summary_and_student_view(self) -> None:
        start = date(2026, 9, 1)
        for day, status in enumerate(["PRESENT", "PRESENT", "LATE", "ABSENT"]):
            Attendance.objects.create(enrolment=self.rahul, date=start + timedelta(days=day), status=status)

        self.act_as(self.faculty)
        response = self.client.get(f"/api/attendance/summary/?course={self.python.id}")
        rows = {row["student"]["student_code"]: row for row in response.json()["data"]["students"]}
        rahul = rows[self.student.student_profile.student_code]
        self.assertEqual((rahul["total_classes"], rahul["absent"], rahul["attendance_percentage"]), (4, 1, 75.0))
        self.assertIsNone(rows[self.classmate.student_profile.student_code]["attendance_percentage"])
        self.assertEqual(self.client.get(f"/api/attendance/summary/?course={self.django.id}").status_code, 400)

        self.act_as(self.student)
        courses = self.client.get("/api/student/attendance/").json()["data"]["courses"]
        python = next(course for course in courses if course["course"]["id"] == self.python.id)
        self.assertEqual(python["summary"]["attendance_percentage"], 75.0)
        self.assertEqual(len(python["records"]), 4)
        only_django = self.client.get(f"/api/student/attendance/?course={self.django.id}").json()["data"]["courses"]
        self.assertEqual(len(only_django), 1)

    def test_update_delete_and_list(self) -> None:
        attendance = Attendance.objects.create(enrolment=self.rahul, date=date(2026, 10, 1), status="ABSENT")
        other = Attendance.objects.create(enrolment=self.other_course, date=date(2026, 10, 1), status="ABSENT")
        self.act_as(self.faculty)

        self.assertEqual(self.client.get("/api/attendance/").json()["data"]["count"], 1)
        self.assertEqual(self.client.get(f"/api/attendance/{other.id}/").status_code, 404)
        response = self.client.patch(f"/api/attendance/{attendance.id}/", {"status": "PRESENT"}, format="json")
        self.assertEqual(response.json()["data"]["attendance"]["status"], "PRESENT")
        self.assertEqual(self.client.delete(f"/api/attendance/{attendance.id}/").status_code, 200)

        self.act_as(self.admin)
        self.assertEqual(self.client.get("/api/attendance/?date=2026-10-01").json()["data"]["count"], 1)

    def test_students_cannot_mark_attendance(self) -> None:
        self.act_as(self.student)
        self.assertEqual(self.record("2026-10-01", [{"enrolment": self.rahul.id, "status": "PRESENT"}]).status_code, 403)
