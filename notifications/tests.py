from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from assessments.models import Assessment
from assignments.models import Assignment
from attendance.models import Attendance
from enrolments.tests import PASSWORD, AcademicTestData
from notifications.models import Notification
from permissions.models import RolePermission

TODAY = timezone.localdate()


class NotificationTestData(AcademicTestData):
    def setUp(self) -> None:
        super().setUp()
        self.rahul = self.enrol(self.student, self.python)
        self.priya = self.enrol(self.classmate, self.django)

    def titles(self, user, notification_type=None) -> list[str]:
        notifications = Notification.objects.filter(recipient=user)
        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)
        return list(notifications.values_list("title", flat=True))


class AutomaticNotificationTests(NotificationTestData):
    def test_enrolment_and_status_change(self) -> None:
        self.assertEqual(self.titles(self.student, "COURSE"), ["Enrolment confirmed"])
        self.rahul.status = "COMPLETED"
        self.rahul.save()
        self.assertIn("Enrolment status updated", self.titles(self.student, "COURSE"))
        self.rahul.save()
        self.assertEqual(len(self.titles(self.student, "COURSE")), 2)

    def test_new_assignment_goes_to_active_students_of_the_course(self) -> None:
        self.act_as(self.faculty)
        data = {"course": self.python.id, "title": "Loops", "due_date": str(TODAY + timedelta(days=5))}
        self.assertEqual(self.client.post("/api/assignments/", data, format="json").status_code, 201)
        self.assertEqual(self.titles(self.student, "ASSIGNMENT"), ["New assignment: Loops"])
        self.assertEqual(self.titles(self.classmate, "ASSIGNMENT"), [])
        self.assertEqual(Notification.objects.get(recipient=self.student, notification_type="ASSIGNMENT").sent_by, self.faculty)

    def test_submission_tells_faculty_and_grading_tells_student(self) -> None:
        homework = Assignment.objects.create(course=self.python, title="Loops", due_date=TODAY + timedelta(days=5))
        self.act_as(self.student)
        self.client.post(f"/api/student/assignments/{homework.id}/submit/", {"submission_text": "done"}, format="json")
        self.assertEqual(self.titles(self.faculty, "ASSIGNMENT"), ["Assignment submitted: Loops"])

        self.act_as(self.faculty)
        records = [{"enrolment": self.rahul.id, "marks": 80}]
        self.client.post(f"/api/assignments/{homework.id}/submissions/", {"records": records}, format="json")
        self.assertIn("Assignment graded: Loops", self.titles(self.student, "ASSIGNMENT"))

    def test_grading_without_submission_does_not_tell_faculty(self) -> None:
        homework = Assignment.objects.create(course=self.python, title="Loops", due_date=TODAY)
        self.act_as(self.faculty)
        self.client.post(f"/api/assignments/{homework.id}/submissions/", {"records": [{"enrolment": self.rahul.id, "marks": 50}]}, format="json")
        self.assertEqual(self.titles(self.faculty, "ASSIGNMENT"), [])

    def test_assessment_and_result(self) -> None:
        self.act_as(self.faculty)
        data = {"course": self.python.id, "title": "Mock Test 1", "assessment_date": str(TODAY)}
        assessment_id = self.client.post("/api/assessments/", data, format="json").json()["data"]["assessment"]["id"]
        self.assertEqual(self.titles(self.student, "ASSESSMENT"), ["New mock test: Mock Test 1"])

        self.client.post(f"/api/assessments/{assessment_id}/results/", {"records": [{"enrolment": self.rahul.id, "marks_obtained": 72}]}, format="json")
        result = Notification.objects.get(recipient=self.student, title="Result published: Mock Test 1")
        self.assertIn("72 / 100 (PASS)", result.message)

    def add_attendance(self, status, count) -> None:
        for _ in range(count):
            self.day += 1
            Attendance.objects.create(enrolment=self.rahul, date=TODAY - timedelta(days=self.day), status=status)

    def test_academic_alert_is_sent_once_while_unread(self) -> None:
        self.day = 0
        self.add_attendance("ABSENT", 1)
        self.assertEqual(self.titles(self.student, "ACADEMIC_ALERT"), ["Academic alert: Python Programming"])
        faculty_alerts = self.titles(self.faculty, "ACADEMIC_ALERT")
        self.assertEqual(len(faculty_alerts), 1)
        self.assertIn(self.student.student_profile.student_code, faculty_alerts[0])

        self.add_attendance("PRESENT", 3)
        self.add_attendance("ABSENT", 3)
        self.assertEqual(len(self.titles(self.student, "ACADEMIC_ALERT")), 1)

        Notification.objects.filter(recipient=self.student).update(is_read=True)
        self.add_attendance("PRESENT", 6)
        self.add_attendance("ABSENT", 3)
        self.assertEqual(len(self.titles(self.student, "ACADEMIC_ALERT")), 2)
        self.assertEqual(len(self.titles(self.faculty, "ACADEMIC_ALERT")), 1)

    def test_faculty_registration_and_approval(self) -> None:
        data = {
            "email": "newfaculty@gmail.com", "first_name": "Neha", "last_name": "Das", "phone": "9000000009",
            "password": PASSWORD, "confirm_password": PASSWORD, "role": "FACULTY",
        }
        self.assertEqual(self.client.post("/api/auth/register/", data, format="json").status_code, 201)
        self.assertEqual(self.titles(self.admin, "ADMINISTRATIVE"), ["New faculty registration"])

        faculty = User.objects.get(email="newfaculty@gmail.com")
        faculty.is_active = True
        faculty.save()
        self.assertEqual(self.titles(faculty, "ADMINISTRATIVE"), ["Faculty account approved"])


class MyNotificationApiTests(NotificationTestData):
    def test_list_count_read_and_delete(self) -> None:
        Notification.objects.create(recipient=self.classmate, title="Not mine", message="x")
        self.assertEqual(self.client.get("/api/notifications/").status_code, 401)

        self.act_as(self.student)
        body = self.client.get("/api/notifications/").json()["data"]
        self.assertEqual((body["count"], body["unread_count"]), (1, 1))
        notification_id = body["results"][0]["id"]

        response = self.client.post(f"/api/notifications/{notification_id}/read/")
        self.assertEqual(response.json()["data"]["notification"]["is_read"], True)
        self.assertEqual(self.client.get("/api/notifications/unread-count/").json()["data"]["unread_count"], 0)
        self.assertEqual(self.client.get("/api/notifications/?is_read=false").json()["data"]["count"], 0)
        self.assertEqual(self.client.get("/api/notifications/?notification_type=COURSE").json()["data"]["count"], 1)
        self.assertEqual(self.client.get("/api/notifications/?notification_type=X").status_code, 400)

        other = Notification.objects.get(recipient=self.classmate, title="Not mine")
        self.assertEqual(self.client.get(f"/api/notifications/{other.id}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/notifications/{notification_id}/").status_code, 200)
        self.assertFalse(Notification.objects.filter(pk=notification_id).exists())

    def test_mark_all_as_read(self) -> None:
        Notification.objects.create(recipient=self.student, title="Second", message="x")
        self.act_as(self.student)
        response = self.client.post("/api/notifications/read-all/")
        self.assertEqual(response.json()["data"]["updated"], 2)
        self.assertFalse(Notification.objects.filter(recipient=self.student, is_read=False).exists())

    def test_permission_is_needed(self) -> None:
        RolePermission.objects.filter(role="STUDENT", permission__name="VIEW_NOTIFICATIONS").delete()
        self.act_as(self.student)
        self.assertEqual(self.client.get("/api/notifications/").status_code, 403)


class SendNotificationApiTests(NotificationTestData):
    URL = "/api/admin/notifications/"

    def send(self, **data):
        return self.client.post(self.URL, {"title": "Holiday", "message": "Institute closed on Friday.", **data}, format="json")

    def test_admin_sends_to_each_audience(self) -> None:
        self.act_as(self.admin)
        self.assertEqual(self.send(audience="STUDENTS").json()["data"]["recipients"], 2)
        self.assertEqual(self.send(audience="FACULTY").json()["data"]["recipients"], 2)
        self.assertEqual(self.send(audience="ALL").json()["data"]["recipients"], 4)
        self.assertEqual(self.send(audience="COURSE", course=self.python.id).json()["data"]["recipients"], 1)
        self.assertEqual(self.send(audience="USER", user=str(self.classmate.id), notification_type="ACADEMIC_ALERT").status_code, 201)
        self.assertIn("Holiday", self.titles(self.classmate, "ACADEMIC_ALERT"))
        self.assertEqual(Notification.objects.filter(title="Holiday", recipient=self.student).first().notification_type, "ADMINISTRATIVE")

    def test_validation(self) -> None:
        self.act_as(self.admin)
        self.assertEqual(set(self.send(audience="COURSE").json()["errors"]), {"course"})
        self.assertEqual(set(self.send(audience="USER").json()["errors"]), {"user"})
        self.assertEqual(set(self.client.post(self.URL, {"audience": "ALL"}, format="json").json()["errors"]), {"title", "message"})
        self.assertEqual(self.send(audience="COURSE", course=self.draft.id).status_code, 400)

    def test_faculty_needs_permission_and_only_own_courses(self) -> None:
        self.act_as(self.faculty)
        self.assertEqual(self.send(audience="COURSE", course=self.python.id).status_code, 403)

        RolePermission.objects.create(role="FACULTY", permission_id=RolePermission.objects.filter(permission__name="SEND_NOTIFICATIONS").first().permission_id)
        self.assertEqual(self.send(audience="COURSE", course=self.python.id).status_code, 201)
        self.assertEqual(set(self.send(audience="STUDENTS").json()["errors"]), {"audience"})
        self.assertEqual(set(self.send(audience="COURSE", course=self.django.id).json()["errors"]), {"course"})
        self.assertEqual(self.client.get(self.URL).json()["data"]["count"], 1)

    def test_history_and_delete(self) -> None:
        self.act_as(self.admin)
        self.send(audience="STUDENTS")
        body = self.client.get(f"{self.URL}?search=holiday").json()["data"]
        self.assertEqual(body["count"], 2)
        self.assertEqual(self.client.get(f"{self.URL}?recipient={self.student.id}&search=holiday").json()["data"]["count"], 1)
        self.assertEqual(self.client.delete(f"{self.URL}{body['results'][0]['id']}/").status_code, 200)
        self.assertEqual(self.client.get(f"{self.URL}?search=holiday").json()["data"]["count"], 1)

    def test_students_cannot_send(self) -> None:
        self.act_as(self.student)
        self.assertEqual(self.send(audience="ALL").status_code, 403)