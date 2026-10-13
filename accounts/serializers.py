from rest_framework import serializers
from accounts.models import User, FacultyProfile


# A serializer only converts a model object into JSON data (the response). Validation of the incoming data is done by the ModelForms in forms.py.
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "full_name", "phone", "role", "role_display", "is_active", "email_verified", "date_joined", "last_login")
        read_only_fields = fields


class FacultyProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = FacultyProfile
        fields = ("id", "employee_code", "user", "designation", "expertise", "bio", "photo", "created_at", "updated_at")
        read_only_fields = fields