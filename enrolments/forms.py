from django import forms
from django.core.exceptions import ValidationError
from courses.models import Course
from courses.views.api_views import published_courses
from enrolments.models import Enrolment
from students.models import StudentProfile


class EnrolForm(forms.ModelForm):
    class Meta:
        model = Enrolment
        fields: tuple = ("course",)

    def __init__(self, *args, student: StudentProfile, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.fields["course"].queryset = published_courses()
        self.fields["course"].error_messages["invalid_choice"] = "Select a published course."

    def clean_course(self):
        course = self.cleaned_data["course"]
        enrolment = Enrolment.objects.filter(student=self.student, course=course).first()
        if enrolment and enrolment.status == Enrolment.Status.DROPPED:
            raise ValidationError("You dropped this course earlier. Please contact the administrator to re-activate your enrolment.")
        if enrolment:
            raise ValidationError("You are already enrolled in this course.")
        return course

    def save(self) -> Enrolment:
        enrolment = super().save(commit=False)
        enrolment.student = self.student
        enrolment.save()
        return enrolment


class EnrolmentUpdateForm(forms.ModelForm):
    FIELDS_WITH_DEFAULTS = ("status", "enrolled_on")

    class Meta:
        model = Enrolment
        fields: tuple = ("status", "enrolled_on", "start_date", "end_date")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.FIELDS_WITH_DEFAULTS:
            self.fields[name].required = False

    def clean(self):
        cleaned_data = super().clean()
        for name in self.FIELDS_WITH_DEFAULTS:
            if not cleaned_data.get(name):
                cleaned_data[name] = Enrolment._meta.get_field(name).get_default()

        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date must be on or after the start date.")
        return cleaned_data


class EnrolmentCreateForm(EnrolmentUpdateForm):
    class Meta(EnrolmentUpdateForm.Meta):
        fields: tuple = ("student", "course") + EnrolmentUpdateForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = StudentProfile.objects.filter(user__is_active=True)
        self.fields["student"].error_messages["invalid_choice"] = "Select an active student."
        self.fields["course"].queryset = Course.objects.exclude(status=Course.Status.ARCHIVED)
        self.fields["course"].error_messages["invalid_choice"] = "Select a course that is not archived."


class EnrolmentFilterForm(forms.Form):
    search = forms.CharField(required=False)
    course = forms.IntegerField(required=False)
    status = forms.ChoiceField(choices=Enrolment.Status.choices, required=False)


class StudentCourseFilterForm(forms.Form):
    course = forms.IntegerField(required=False)