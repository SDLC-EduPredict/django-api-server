from django import forms
from courses.models import Course

EXPORT_CHOICES = [("csv", "CSV file")]


class CourseReportFilterForm(forms.Form):
    search = forms.CharField(required=False)
    category = forms.IntegerField(required=False)
    status = forms.ChoiceField(choices=Course.Status.choices, required=False)
    export = forms.ChoiceField(choices=EXPORT_CHOICES, required=False)


class AttentionReportFilterForm(forms.Form):
    search = forms.CharField(required=False)
    course = forms.IntegerField(required=False)
    export = forms.ChoiceField(choices=EXPORT_CHOICES, required=False)


class PredictionReportFilterForm(forms.Form):
    course = forms.IntegerField(required=False)