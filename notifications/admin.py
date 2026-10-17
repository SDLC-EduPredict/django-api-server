from django.contrib import admin
from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "notification_type", "course", "is_read", "sent_by", "created_at")
    list_filter = ("notification_type", "is_read", "course")
    search_fields = ("title", "message", "recipient__email", "recipient__first_name", "recipient__last_name")
    list_select_related = ("recipient", "course", "sent_by")
    autocomplete_fields = ("recipient", "sent_by")
    readonly_fields = ("read_at", "created_at", "updated_at")