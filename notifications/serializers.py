from rest_framework import serializers
from accounts.models import User
from enrolments.serializers import CourseShortSerializer
from notifications.models import Notification


class RecipientSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ("id", "full_name", "email", "role")
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source="get_notification_type_display", read_only=True)
    course = CourseShortSerializer(read_only=True)
    sent_by = serializers.CharField(source="sent_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = Notification
        fields = (
            "id", "notification_type", "notification_type_display", "title", "message", "course", "sent_by",
            "is_read", "read_at", "created_at")
        read_only_fields = fields


class AdminNotificationSerializer(NotificationSerializer):
    recipient = RecipientSerializer(read_only=True)

    class Meta(NotificationSerializer.Meta):
        fields = ("id", "recipient") + NotificationSerializer.Meta.fields[1:]
        read_only_fields = fields