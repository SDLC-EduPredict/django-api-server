from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.utils import timezone
from assignments.models import Assignment, AssignmentSubmission

MAX_FILE_SIZE_MB = 5
SUBMISSION_STATUS_CHOICES = [
    ("PENDING", "Pending"),
    ("OVERDUE", "Overdue"),
    ("SUBMITTED", "Submitted"),
    ("GRADED", "Graded"),
]


class AssignmentUpdateForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields: tuple = ("title", "description", "due_date", "max_marks")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["max_marks"].required = False

    def clean_max_marks(self):
        max_marks = self.cleaned_data.get("max_marks") or Assignment._meta.get_field("max_marks").default
        if self.instance.pk:
            highest = self.instance.submissions.aggregate(highest=Max("marks"))["highest"]
            if highest is not None and highest > max_marks:
                raise ValidationError(f"Some students already have {highest} marks. Max marks cannot be lower than that.")
        return max_marks


class AssignmentCreateForm(AssignmentUpdateForm):
    class Meta(AssignmentUpdateForm.Meta):
        fields: tuple = ("course",) + AssignmentUpdateForm.Meta.fields

    def __init__(self, *args, courses, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = courses
        self.fields["course"].error_messages["invalid_choice"] = "Select a course you manage."


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields: tuple = ("submission_text", "submission_link", "submission_file")

    def clean_submission_file(self):
        file = self.cleaned_data.get("submission_file")
        if file and file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValidationError(f"File size must be {MAX_FILE_SIZE_MB} MB or less.")
        return file

    def clean(self):
        cleaned_data = super().clean()
        answers = [cleaned_data.get(name) for name in self.Meta.fields]
        if not any(answers) and not self.errors:
            raise ValidationError("Send at least one of submission_text, submission_link or submission_file.")
        return cleaned_data

    def save(self) -> AssignmentSubmission:
        submission = super().save(commit=False)
        submission.status = AssignmentSubmission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save()
        return submission


class AssignmentMarksForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields: tuple = ("enrolment", "marks", "feedback")

    def __init__(self, *args, assignment, enrolments, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        self.user = user
        self.fields["marks"].required = True
        self.fields["enrolment"].queryset = enrolments
        self.fields["enrolment"].error_messages["invalid_choice"] = "Select an active or completed enrolment of this course."

    def clean_marks(self):
        marks = self.cleaned_data["marks"]
        if marks > self.assignment.max_marks:
            raise ValidationError(f"Marks cannot be more than {self.assignment.max_marks}.")
        return marks

    def save(self) -> AssignmentSubmission:
        submission, _ = AssignmentSubmission.objects.get_or_create(assignment=self.assignment, enrolment=self.cleaned_data["enrolment"])
        submission.marks = self.cleaned_data["marks"]
        submission.feedback = self.cleaned_data["feedback"]
        submission.status = AssignmentSubmission.Status.GRADED
        submission.graded_by = self.user
        submission.graded_at = timezone.now()
        submission.save()
        return submission


class AssignmentFilterForm(forms.Form):
    course = forms.IntegerField(required=False)
    search = forms.CharField(required=False)


class StudentAssignmentFilterForm(forms.Form):
    course = forms.IntegerField(required=False)
    status = forms.ChoiceField(choices=SUBMISSION_STATUS_CHOICES, required=False)