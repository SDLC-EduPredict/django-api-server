from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from attendance.models import Attendance


class AttendanceSheetForm(forms.Form):
    date = forms.DateField()

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date > timezone.localdate():
            raise ValidationError("Attendance cannot be recorded for a future date.")
        return date


class AttendanceRecordForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields: tuple = ("enrolment", "status", "remarks")

    def __init__(self, *args, enrolments, date, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.date = date
        self.user = user
        self.fields["enrolment"].queryset = enrolments
        self.fields["enrolment"].error_messages["invalid_choice"] = "Select an active enrolment of a course you manage."

    def save(self) -> Attendance:
        attendance, _ = Attendance.objects.update_or_create(
            enrolment=self.cleaned_data["enrolment"],
            date=self.date,
            defaults={
                "status": self.cleaned_data["status"],
                "remarks": self.cleaned_data["remarks"],
                "marked_by": self.user,
            })
        return attendance


class AttendanceUpdateForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields: tuple = ("status", "remarks")


class AttendanceFilterForm(forms.Form):
    course = forms.IntegerField(required=False)
    enrolment = forms.IntegerField(required=False)
    status = forms.ChoiceField(choices=Attendance.Status.choices, required=False)
    date = forms.DateField(required=False)
    date_from = forms.DateField(required=False)
    date_to = forms.DateField(required=False)
    search = forms.CharField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "date_to must be on or after date_from.")
        return cleaned_data


class AttendanceSummaryForm(forms.Form):
    course = forms.ModelChoiceField(queryset=None, error_messages={"invalid_choice": "Select a course you manage."})

    def __init__(self, *args, courses, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = courses
