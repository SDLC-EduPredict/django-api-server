from rest_framework import serializers
from permissions.models import Permission


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("id", "name", "description")
        read_only_fields = fields