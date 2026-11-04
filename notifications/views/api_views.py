import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required, role_required
from accounts.models import User
from core.responses import error_response, paginated_response, success_response
from enrolments.utils import STAFF_ROLES
from notifications.forms import AdminNotificationFilterForm, NotificationFilterForm, SendNotificationForm
from notifications.models import Notification
from notifications.serializers import AdminNotificationSerializer, NotificationSerializer
from permissions.constants import SEND_NOTIFICATIONS, VIEW_NOTIFICATIONS
from permissions.decorators import permission_required

logger = logging.getLogger(__name__)


def my_notifications(user):
    return Notification.objects.select_related("course", "sent_by").filter(recipient=user)


def unread_count(user) -> int:
    return Notification.objects.filter(recipient=user, is_read=False).count()


def sent_notifications(user):
    notifications = Notification.objects.select_related("recipient", "course", "sent_by")
    if user.role == User.Role.FACULTY:
        return notifications.filter(sent_by=user)
    return notifications


def filter_notifications(notifications, filters):
    if filters["is_read"] is not None:
        notifications = notifications.filter(is_read=filters["is_read"])
    if filters["notification_type"]:
        notifications = notifications.filter(notification_type=filters["notification_type"])
    if filters["course"]:
        notifications = notifications.filter(course_id=filters["course"])
    return notifications


@api_view(["GET"])
@jwt_required
@permission_required(VIEW_NOTIFICATIONS)
def notification_list(request):
    form = NotificationFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid filter values.", form.errors)

    notifications = filter_notifications(my_notifications(request.user), form.cleaned_data)
    response = paginated_response(request, notifications, NotificationSerializer, "Notifications fetched successfully.")
    response.data["data"]["unread_count"] = unread_count(request.user)
    return response


@api_view(["GET"])
@jwt_required
@permission_required(VIEW_NOTIFICATIONS)
def notification_unread_count(request):
    return success_response("Unread notifications counted successfully.", {"unread_count": unread_count(request.user)})


@api_view(["GET", "DELETE"])
@jwt_required
@permission_required(VIEW_NOTIFICATIONS)
def notification_detail(request, notification_id):
    notification = my_notifications(request.user).filter(pk=notification_id).first()
    if notification is None:
        return error_response("Notification not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return success_response("Notification fetched successfully.", {"notification": NotificationSerializer(notification).data})

    notification.delete()
    return success_response("Notification deleted successfully!", {"unread_count": unread_count(request.user)})


@api_view(["POST"])
@jwt_required
@permission_required(VIEW_NOTIFICATIONS)
def notification_mark_read(request, notification_id):
    notification = my_notifications(request.user).filter(pk=notification_id).first()
    if notification is None:
        return error_response("Notification not found.", status_code=status.HTTP_404_NOT_FOUND)

    notification.mark_as_read()
    return success_response("Notification marked as read.", {
        "notification": NotificationSerializer(notification).data,
        "unread_count": unread_count(request.user),
    })


@api_view(["POST"])
@jwt_required
@permission_required(VIEW_NOTIFICATIONS)
def notification_mark_all_read(request):
    updated = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
    return success_response(f"{updated} notification(s) marked as read.", {"updated": updated, "unread_count": 0})


@api_view(["GET", "POST"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(SEND_NOTIFICATIONS)
def admin_notification_list_send(request):
    if request.method == "GET":
        form = AdminNotificationFilterForm(request.query_params)
        if not form.is_valid():
            return error_response("Invalid search or filter values.", form.errors)

        filters = form.cleaned_data
        notifications = filter_notifications(sent_notifications(request.user), filters)
        if filters["recipient"]:
            notifications = notifications.filter(recipient_id=filters["recipient"])
        for word in filters["search"].split():
            notifications = notifications.filter(
                Q(title__icontains=word) | Q(message__icontains=word) | Q(recipient__email__icontains=word)
                | Q(recipient__first_name__icontains=word) | Q(recipient__last_name__icontains=word))
        return paginated_response(request, notifications, AdminNotificationSerializer, "Notifications fetched successfully.")

    form = SendNotificationForm(request.data, sender=request.user)
    if not form.is_valid():
        return error_response("Notification could not be sent.", form.errors)

    count = form.save()
    if count == 0:
        return error_response("No active user matches this audience, so nothing was sent.")

    logger.info("Notification '%s' sent to %s user(s) by %s", form.cleaned_data["title"], count, request.user.email)
    return success_response(f"Notification sent to {count} user(s).", {"recipients": count}, status.HTTP_201_CREATED)


@api_view(["DELETE"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(SEND_NOTIFICATIONS)
def admin_notification_delete(request, notification_id):
    notification = sent_notifications(request.user).filter(pk=notification_id).first()
    if notification is None:
        return error_response("Notification not found.", status_code=status.HTTP_404_NOT_FOUND)

    notification.delete()
    logger.info("Notification %s deleted by %s", notification_id, request.user.email)
    return success_response("Notification deleted successfully!")