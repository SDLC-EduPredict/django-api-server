from rest_framework import serializers
from assessments.utils import assessment_summary
from assignments.utils import assignment_summary
from attendance.utils import attendance_summary
from courses.models import Course
from courses.serializers import CourseListSerializer
from enrolments.models import Enrolment
from students.models import StudentProfile


class StudentShortSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = StudentProfile
        fields = ("id", "student_code", "full_name", "email")
        read_only_fields = fields


class CourseShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ("id", "title", "slug")
        read_only_fields = fields


class EnrolmentSerializer(serializers.ModelSerializer):
    student = StudentShortSerializer(read_only=True)
    course = CourseShortSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Enrolment
        fields = ("id", "student", "course", "status", "status_display", "enrolled_on", "start_date", "end_date", "created_at", "updated_at")
        read_only_fields = fields


class EnrolmentDetailSerializer(EnrolmentSerializer):
    progress = serializers.SerializerMethodField()

    class Meta(EnrolmentSerializer.Meta):
        fields = EnrolmentSerializer.Meta.fields + ("progress",)
        read_only_fields = fields

    def get_progress(self, enrolment) -> dict:
        return {
            "attendance": attendance_summary(enrolment),
            "assignments": assignment_summary(enrolment),
            "assessments": assessment_summary(enrolment),
        }


class StudentEnrolmentSerializer(EnrolmentDetailSerializer):
    course = CourseListSerializer(read_only=True)

    class Meta(EnrolmentDetailSerializer.Meta):
        fields = ("id", "course", "status", "status_display", "enrolled_on", "start_date", "end_date", "progress")
        read_only_fields = fields
