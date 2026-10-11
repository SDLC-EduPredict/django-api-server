from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from students.models import StudentProfile


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields: tuple = ("date_of_birth", "gender", "highest_qualification", "address", "city", "photo")

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data.get("date_of_birth")
        if date_of_birth and date_of_birth >= timezone.localdate():
            raise ValidationError("Date of birth must be in the past.")
        return date_of_birth


class StudentFilterForm(forms.Form):
    search = forms.CharField(required=False)
    city = forms.CharField(required=False)
    gender = forms.ChoiceField(choices=StudentProfile.Gender.choices, required=False)
    is_active = forms.NullBooleanField(required=False)