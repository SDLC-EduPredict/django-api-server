from django import forms
from django.core.exceptions import ValidationError
from accounts.models import User
from enrolments.utils import staff_courses
from notifications.models import Notification
from notifications.utils import course_student_users, notify


class NotificationFilterForm(forms.Form):
    is_read = forms.NullBooleanField(required=False)
    notification_type = forms.ChoiceField(choices=Notification.Type.choices, required=False)
    course = forms.IntegerField(required=False)


class AdminNotificationFilterForm(NotificationFilterForm):
    search = forms.CharField(required=False)
    recipient = forms.UUIDField(required=False)


class SendNotificationForm(forms.ModelForm):
    ALL = "ALL"
    STUDENTS = "STUDENTS"
    FACULTY = "FACULTY"
    COURSE = "COURSE"
    USER = "USER"
    AUDIENCE_CHOICES = [
        (ALL, "All active users"),
        (STUDENTS, "All active students"),
        (FACULTY, "All active faculty"),
        (COURSE, "Active students of one course"),
        (USER, "One user"),
    ]

    audience = forms.ChoiceField(choices=AUDIENCE_CHOICES)
    user = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True), required=False, error_messages={"invalid_choice": "Select an active user."})

    class Meta:
        model = Notification
        fields: tuple = ("notification_type", "title", "message", "course")

    def __init__(self, *args, sender, **kwargs):
        super().__init__(*args, **kwargs)
        self.sender = sender
        self.fields["notification_type"].required = False
        self.fields["course"].queryset = staff_courses(sender)
        self.fields["course"].error_messages["invalid_choice"] = "Select a course you manage."

    def clean(self):
        cleaned_data = super().clean()
        audience = cleaned_data.get("audience")

        if not cleaned_data.get("notification_type"):
            cleaned_data["notification_type"] = Notification.Type.ADMINISTRATIVE
        if self.sender.role == User.Role.FACULTY and audience and audience != self.COURSE:
            self.add_error("audience", "Faculty can send notifications only to the students of their own courses (audience COURSE).")
        if audience == self.COURSE and not cleaned_data.get("course"):
            self.add_error("course", "Select the course whose students should get this notification.")
        if audience == self.USER and not cleaned_data.get("user"):
            self.add_error("user", "Select the user who should get this notification.")
        return cleaned_data

    def recipients(self):
        audience = self.cleaned_data["audience"]
        active_users = User.objects.filter(is_active=True)

        if audience == self.STUDENTS:
            return active_users.filter(role=User.Role.STUDENT)
        if audience == self.FACULTY:
            return active_users.filter(role=User.Role.FACULTY)
        if audience == self.COURSE:
            return course_student_users(self.cleaned_data["course"])
        if audience == self.USER:
            return [self.cleaned_data["user"]]
        return active_users.exclude(pk=self.sender.pk)

    def save(self) -> int:
        data = self.cleaned_data
        return notify(
            self.recipients(), data["notification_type"], data["title"], data["message"],
            course=data["course"], sent_by=self.sender)