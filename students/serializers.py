from rest_framework import serializers
from accounts.serializers import UserSerializer
from students.models import StudentProfile


class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    gender_display = serializers.CharField(source="get_gender_display", read_only=True)
    profile_completion = serializers.IntegerField(read_only=True)
    missing_profile_fields = serializers.ListField(read_only=True)

    class Meta:
        model = StudentProfile
        fields = (
            "id", "student_code", "user", "date_of_birth", "gender", "gender_display", "highest_qualification",
            "address", "city", "photo", "profile_completion", "missing_profile_fields", "created_at", "updated_at")
        read_only_fields = fields