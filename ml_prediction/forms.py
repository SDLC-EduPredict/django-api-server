from django import forms
from django.core.exceptions import ValidationError
from enrolments.models import Enrolment
from enrolments.utils import GRADABLE_STATUSES
from ml_prediction.models import MLModelVersion, Prediction
from performance.models import Performance


class PredictionInputForm(forms.ModelForm):
    class Meta:
        model = Prediction
        fields: tuple = tuple(Prediction.FEATURES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True

    def feature_values(self) -> dict:
        return {feature: float(self.cleaned_data[feature]) for feature in Prediction.FEATURES}


class EnrolmentPredictionForm(forms.Form):
    enrolment = forms.ModelChoiceField(queryset=None, error_messages={"invalid_choice": "Select an active or completed enrolment."})

    def __init__(self, *args, enrolments, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["enrolment"].queryset = enrolments.filter(status__in=GRADABLE_STATUSES)


class PredictionFilterForm(forms.Form):
    ORDERING_CHOICES = [
        ("predicted_final_score", "Lowest predicted score first"),
        ("-predicted_final_score", "Highest predicted score first"),
        ("enrolment__student__student_code", "Student code"),
    ]

    search = forms.CharField(required=False)
    course = forms.IntegerField(required=False)
    status = forms.ChoiceField(choices=Enrolment.Status.choices, required=False)
    indicator = forms.ChoiceField(choices=Performance.Indicator.choices, required=False)
    ordering = forms.ChoiceField(choices=ORDERING_CHOICES, required=False)


class TrainModelForm(forms.Form):
    source = forms.ChoiceField(choices=MLModelVersion.DataSource.choices, required=False)
    file = forms.FileField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get("source") or MLModelVersion.DataSource.SAMPLE
        file = cleaned_data.get("file")

        if file and source == MLModelVersion.DataSource.SAMPLE:
            source = MLModelVersion.DataSource.CSV
        if source == MLModelVersion.DataSource.CSV and not file:
            self.add_error("file", "Upload a CSV file when the source is CSV.")
        if file and not file.name.lower().endswith(".csv"):
            self.add_error("file", "Only .csv files are allowed.")

        cleaned_data["source"] = source
        return cleaned_data