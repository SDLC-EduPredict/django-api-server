from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.utils import timezone
from assessments.models import Assessment, AssessmentResult


class AssessmentUpdateForm(forms.ModelForm):
    FIELDS_WITH_DEFAULTS = ("assessment_type", "max_marks", "pass_marks")

    class Meta:
        model = Assessment
        fields: tuple = ("title", "assessment_type", "description", "assessment_date", "max_marks", "pass_marks")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.FIELDS_WITH_DEFAULTS:
            self.fields[name].required = False

    def clean(self):
        cleaned_data = super().clean()
        for name in self.FIELDS_WITH_DEFAULTS:
            if cleaned_data.get(name) in (None, ""):
                cleaned_data[name] = Assessment._meta.get_field(name).default

        max_marks = cleaned_data["max_marks"]
        if cleaned_data["pass_marks"] > max_marks:
            self.add_error("pass_marks", "Pass marks cannot be more than max marks.")

        if self.instance.pk:
            highest = self.instance.results.aggregate(highest=Max("marks_obtained"))["highest"]
            if highest is not None and highest > max_marks:
                self.add_error("max_marks", f"Some students already have {highest} marks. Max marks cannot be lower than that.")
        return cleaned_data


class AssessmentCreateForm(AssessmentUpdateForm):
    class Meta(AssessmentUpdateForm.Meta):
        fields: tuple = ("course",) + AssessmentUpdateForm.Meta.fields

    def __init__(self, *args, courses, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = courses
        self.fields["course"].error_messages["invalid_choice"] = "Select a course you manage."


class AssessmentResultForm(forms.ModelForm):
    class Meta:
        model = AssessmentResult
        fields: tuple = ("enrolment", "marks_obtained", "remarks")

    def __init__(self, *args, assessment, enrolments, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.assessment = assessment
        self.user = user
        self.fields["enrolment"].queryset = enrolments
        self.fields["enrolment"].error_messages["invalid_choice"] = "Select an active or completed enrolment of this course."

    def clean_marks_obtained(self):
        marks = self.cleaned_data["marks_obtained"]
        if marks > self.assessment.max_marks:
            raise ValidationError(f"Marks cannot be more than {self.assessment.max_marks}.")
        return marks

    def clean(self):
        cleaned_data = super().clean()
        if self.assessment.assessment_date > timezone.localdate():
            raise ValidationError(f"Marks can be entered only on or after the assessment date ({self.assessment.assessment_date}).")
        return cleaned_data

    def save(self) -> AssessmentResult:
        result, _ = AssessmentResult.objects.update_or_create(
            assessment=self.assessment,
            enrolment=self.cleaned_data["enrolment"],
            defaults={
                "marks_obtained": self.cleaned_data["marks_obtained"],
                "remarks": self.cleaned_data["remarks"],
                "entered_by": self.user,
            })
        return result


class AssessmentFilterForm(forms.Form):
    course = forms.IntegerField(required=False)
    assessment_type = forms.ChoiceField(choices=Assessment.Type.choices, required=False)
    search = forms.CharField(required=False)


class StudentResultFilterForm(forms.Form):
    course = forms.IntegerField(required=False)
    assessment_type = forms.ChoiceField(choices=Assessment.Type.choices, required=False)
