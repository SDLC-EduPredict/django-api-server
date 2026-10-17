from rest_framework import serializers
from analytics.utils import attention_reasons
from assignments.models import AssignmentSubmission
from courses.models import Course
from enrolments.serializers import StudentShortSerializer
from performance.models import Performance


class CoursePerformanceSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.name", read_only=True)
    faculty = serializers.CharField(source="faculty.get_full_name", read_only=True, default=None)
    students = serializers.IntegerField(read_only=True)
    average_attendance = serializers.FloatField(read_only=True)
    average_assignment_score = serializers.FloatField(read_only=True)
    average_assessment_score = serializers.FloatField(read_only=True)
    average_performance = serializers.FloatField(read_only=True)
    average_predicted_score = serializers.FloatField(read_only=True)
    low_attendance_students = serializers.IntegerField(read_only=True)
    good = serializers.IntegerField(read_only=True)
    average = serializers.IntegerField(read_only=True)
    needs_attention = serializers.IntegerField(read_only=True)
    no_data = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = (
            "id", "title", "category", "faculty", "status", "students", "average_attendance", "average_assignment_score",
            "average_assessment_score", "average_performance", "average_predicted_score", "low_attendance_students",
            "good", "average", "needs_attention", "no_data")
        read_only_fields = fields

    def to_representation(self, course):
        data = super().to_representation(course)
        for field in ("average_attendance", "average_assignment_score", "average_assessment_score", "average_performance", "average_predicted_score"):
            if data[field] is not None:
                data[field] = round(data[field], 2)
        return data


class StudentProgressSerializer(serializers.ModelSerializer):
    enrolment_status = serializers.CharField(source="enrolment.status", read_only=True)
    student_id = serializers.IntegerField(source="enrolment.student.id", read_only=True)
    student_code = serializers.CharField(source="enrolment.student.student_code", read_only=True)
    student_name = serializers.CharField(source="enrolment.student.user.get_full_name", read_only=True)
    email = serializers.EmailField(source="enrolment.student.user.email", read_only=True)
    course_id = serializers.IntegerField(source="enrolment.course.id", read_only=True)
    course = serializers.CharField(source="enrolment.course.title", read_only=True)
    faculty = serializers.CharField(source="enrolment.course.faculty.get_full_name", read_only=True, default=None)
    attendance_percentage = serializers.FloatField(read_only=True)
    assignment_average = serializers.FloatField(read_only=True)
    mock_test_average = serializers.FloatField(read_only=True)
    exam_average = serializers.FloatField(read_only=True)
    assessment_average = serializers.FloatField(read_only=True)
    overall_score = serializers.FloatField(read_only=True)
    predicted_final_score = serializers.FloatField(source="enrolment.prediction.predicted_final_score", read_only=True, default=None)
    prediction_indicator = serializers.CharField(source="enrolment.prediction.indicator", read_only=True, default=None)
    reasons = serializers.SerializerMethodField()

    class Meta:
        model = Performance
        fields = (
            "id", "enrolment", "enrolment_status", "student_id", "student_code", "student_name", "email", "course_id",
            "course", "faculty", "attendance_percentage", "assignment_average", "mock_test_average", "exam_average",
            "assessment_average", "overall_score", "indicator", "predicted_final_score", "prediction_indicator", "reasons")
        read_only_fields = fields

    def get_reasons(self, performance) -> list[str]:
        return attention_reasons(performance)


class PendingSubmissionSerializer(serializers.ModelSerializer):
    assignment_title = serializers.CharField(source="assignment.title", read_only=True)
    course = serializers.CharField(source="assignment.course.title", read_only=True)
    student = StudentShortSerializer(source="enrolment.student", read_only=True)
    is_late = serializers.BooleanField(read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = ("id", "assignment", "assignment_title", "course", "enrolment", "student", "submitted_at", "is_late")
        read_only_fields = fields