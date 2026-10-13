from rest_framework import serializers
from assignments.models import Assignment, AssignmentSubmission
from assignments.utils import submission_status
from enrolments.serializers import CourseShortSerializer


class AssignmentSerializer(serializers.ModelSerializer):
    course = CourseShortSerializer(read_only=True)
    created_by = serializers.CharField(source="created_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = Assignment
        fields = ("id", "course", "title", "description", "due_date", "max_marks", "created_by", "created_at", "updated_at")
        read_only_fields = fields


class SubmissionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    marks = serializers.DecimalField(max_digits=5, decimal_places=2, coerce_to_string=False, read_only=True)
    percentage = serializers.FloatField(read_only=True)
    is_late = serializers.BooleanField(read_only=True)
    graded_by = serializers.CharField(source="graded_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = AssignmentSubmission
        fields = (
            "id", "assignment", "enrolment", "status", "status_display", "submission_text", "submission_link",
            "submission_file", "submitted_at", "is_late", "marks", "percentage", "feedback", "graded_by", "graded_at")
        read_only_fields = fields


class StudentAssignmentSerializer(AssignmentSerializer):
    my_status = serializers.SerializerMethodField()
    my_submission = serializers.SerializerMethodField()

    class Meta(AssignmentSerializer.Meta):
        fields = ("id", "title", "description", "due_date", "max_marks", "my_status", "my_submission")
        read_only_fields = fields

    def my_submission_object(self, assignment):
        return assignment.submissions.filter(enrolment=self.context["enrolment"]).first()

    def get_my_status(self, assignment) -> str:
        return submission_status(assignment, self.my_submission_object(assignment))

    def get_my_submission(self, assignment):
        submission = self.my_submission_object(assignment)
        if submission is None:
            return None
        return SubmissionSerializer(submission, context=self.context).data
