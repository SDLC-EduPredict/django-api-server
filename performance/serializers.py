from rest_framework import serializers
from enrolments.serializers import CourseShortSerializer, StudentShortSerializer
from performance.models import Performance


class PerformanceSerializer(serializers.ModelSerializer):
    attendance_percentage = serializers.FloatField(read_only=True)
    assignment_average = serializers.FloatField(read_only=True)
    mock_test_average = serializers.FloatField(read_only=True)
    exam_average = serializers.FloatField(read_only=True)
    assessment_average = serializers.FloatField(read_only=True)
    practice_hours = serializers.FloatField(read_only=True)
    previous_score = serializers.FloatField(read_only=True)
    total_modules = serializers.IntegerField(source="enrolment.course.total_modules", read_only=True)
    modules_completed_percentage = serializers.FloatField(read_only=True)
    participation_display = serializers.CharField(source="get_participation_display", read_only=True)
    participation_score = serializers.IntegerField(read_only=True)
    overall_score = serializers.FloatField(read_only=True)
    indicator_display = serializers.CharField(source="get_indicator_display", read_only=True)

    class Meta:
        model = Performance
        fields = (
            "id", "attendance_percentage", "assignment_average", "mock_test_average", "exam_average", "assessment_average",
            "practice_hours", "previous_score", "modules_completed", "total_modules", "modules_completed_percentage",
            "participation", "participation_display", "participation_score", "overall_score", "indicator", "indicator_display",
            "calculated_at")
        read_only_fields = fields


class StaffPerformanceSerializer(PerformanceSerializer):
    student = StudentShortSerializer(source="enrolment.student", read_only=True)
    course = CourseShortSerializer(source="enrolment.course", read_only=True)
    enrolment_status = serializers.CharField(source="enrolment.status", read_only=True)
    updated_by = serializers.CharField(source="updated_by.get_full_name", read_only=True, default=None)

    class Meta(PerformanceSerializer.Meta):
        fields = (
            "id", "enrolment", "enrolment_status", "student", "course", "attendance_percentage", "assignment_average",
            "mock_test_average", "exam_average", "assessment_average", "practice_hours", "previous_score", "modules_completed",
            "total_modules", "modules_completed_percentage", "participation", "participation_display", "participation_score",
            "overall_score", "indicator", "indicator_display", "calculated_at", "updated_by", "updated_at")
        read_only_fields = fields


class MLDatasetSerializer(serializers.ModelSerializer):
    enrolment_id = serializers.IntegerField(source="enrolment.id", read_only=True)
    student_code = serializers.CharField(source="enrolment.student.student_code", read_only=True)
    course = serializers.CharField(source="enrolment.course.title", read_only=True)
    attendance = serializers.FloatField(source="attendance_percentage", read_only=True)
    assignment_average = serializers.FloatField(read_only=True)
    mock_test_average = serializers.FloatField(read_only=True)
    practice_hours = serializers.FloatField(read_only=True)
    previous_score = serializers.FloatField(read_only=True)
    modules_completed = serializers.FloatField(source="modules_completed_percentage", read_only=True)
    participation = serializers.IntegerField(source="participation_score", read_only=True)
    final_score = serializers.FloatField(source="exam_average", read_only=True)

    class Meta:
        model = Performance
        fields = (
            "enrolment_id", "student_code", "course", "attendance", "assignment_average", "mock_test_average",
            "practice_hours", "previous_score", "modules_completed", "participation", "final_score")
        read_only_fields = fields