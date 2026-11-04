from django import forms
from enrolments.models import Enrolment
from performance.models import Performance
from performance.utils import calculate_performance, send_indicator_changed


class PerformanceInputForm(forms.ModelForm):
    class Meta:
        model = Performance
        fields: tuple = ("practice_hours", "previous_score", "modules_completed", "participation")

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def save(self) -> Performance:
        performance = super().save(commit=False)
        old_indicator = performance.indicator
        performance.updated_by = self.user
        calculate_performance(performance)
        performance.save()
        send_indicator_changed(performance, old_indicator)
        return performance


class PerformanceFilterForm(forms.Form):
    ORDERING_CHOICES = [
        ("overall_score", "Lowest overall score first"),
        ("-overall_score", "Highest overall score first"),
        ("enrolment__student__student_code", "Student code"),
    ]

    search = forms.CharField(required=False)
    course = forms.IntegerField(required=False)
    enrolment = forms.IntegerField(required=False)
    status = forms.ChoiceField(choices=Enrolment.Status.choices, required=False)
    indicator = forms.ChoiceField(choices=Performance.Indicator.choices, required=False)
    participation = forms.ChoiceField(choices=Performance.Participation.choices, required=False)
    ordering = forms.ChoiceField(choices=ORDERING_CHOICES, required=False)


class PerformanceSummaryForm(forms.Form):
    course = forms.ModelChoiceField(queryset=None, error_messages={"invalid_choice": "Select a course you manage."})

    def __init__(self, *args, courses, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = courses


class DatasetFilterForm(forms.Form):
    EXPORT_CHOICES = [("json", "JSON"), ("csv", "CSV file")]

    course = forms.IntegerField(required=False)