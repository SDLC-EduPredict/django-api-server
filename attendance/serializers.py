from rest_framework import serializers
from attendance.models import Attendance
from enrolments.serializers import CourseShortSerializer, StudentShortSerializer


class AttendanceRecordSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Attendance
        fields = ("id", "date", "status", "status_display", "remarks")
        read_only_fields = fields


class AttendanceSerializer(AttendanceRecordSerializer):
    student = StudentShortSerializer(source="enrolment.student", read_only=True)
    course = CourseShortSerializer(source="enrolment.course", read_only=True)
    marked_by = serializers.CharField(source="marked_by.get_full_name", read_only=True, default=None)

    class Meta(AttendanceRecordSerializer.Meta):
        fields = ("id", "enrolment", "student", "course", "date", "status", "status_display", "remarks", "marked_by", "created_at", "updated_at")
        read_only_fields = fields
