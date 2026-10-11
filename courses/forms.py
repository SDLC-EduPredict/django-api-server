from django import forms
from django.core.exceptions import ValidationError
from accounts.models import User
from courses.models import Course, CourseCategory


class CourseCategoryForm(forms.ModelForm):
    class Meta:
        model = CourseCategory
        fields: tuple = ("name", "slug", "description", "is_active")

    def clean_name(self) -> str:
        name = self.cleaned_data["name"]
        duplicates = CourseCategory.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError("A category with this name already exists.")
        return name


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields: tuple = (
            "category", "faculty", "title", "slug", "short_description", "description", "level", "mode",
            "duration_weeks", "total_modules", "fee", "start_date", "thumbnail", "status", "meta_title", "meta_description")

    FIELDS_WITH_DEFAULTS = ("level", "mode", "status", "fee")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["faculty"].queryset = User.objects.filter(role=User.Role.FACULTY, is_active=True)
        self.fields["faculty"].error_messages["invalid_choice"] = "Select an active faculty member."
        for name in self.FIELDS_WITH_DEFAULTS:
            self.fields[name].required = False

    def clean(self):
        cleaned_data = super().clean()
        for name in self.FIELDS_WITH_DEFAULTS:
            if cleaned_data.get(name) in (None, ""):
                cleaned_data[name] = Course._meta.get_field(name).default
        return cleaned_data


class CourseFilterForm(forms.Form):
    ORDERING_CHOICES = [
        ("-created_at", "Newest first"),
        ("created_at", "Oldest first"),
        ("title", "Title A-Z"),
        ("-title", "Title Z-A"),
        ("fee", "Fee low to high"),
        ("-fee", "Fee high to low"),
        ("start_date", "Starting soon"),
    ]

    search = forms.CharField(required=False)
    category = forms.CharField(required=False)
    level = forms.ChoiceField(choices=Course.Level.choices, required=False)
    mode = forms.ChoiceField(choices=Course.Mode.choices, required=False)
    status = forms.ChoiceField(choices=Course.Status.choices, required=False)
    faculty = forms.UUIDField(required=False)
    min_fee = forms.DecimalField(min_value=0, required=False)
    max_fee = forms.DecimalField(min_value=0, required=False)
    ordering = forms.ChoiceField(choices=ORDERING_CHOICES, required=False)

    def clean(self):
        cleaned_data = super().clean()
        min_fee = cleaned_data.get("min_fee")
        max_fee = cleaned_data.get("max_fee")
        if min_fee is not None and max_fee is not None and min_fee > max_fee:
            self.add_error("max_fee", "max_fee must be greater than or equal to min_fee.")
        return cleaned_data