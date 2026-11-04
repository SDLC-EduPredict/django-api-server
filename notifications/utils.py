from accounts.models import User
from enrolments.models import Enrolment
from notifications.models import Notification

ADMIN_ROLES = (User.Role.ADMIN, User.Role.SUPER_ADMIN)
TITLE_LENGTH = Notification._meta.get_field("title").max_length


def notify(recipients, notification_type, title, message, course=None, sent_by=None) -> int:
    unique_recipients = {user.pk: user for user in recipients if user is not None}
    notifications = [
        Notification(
            recipient=user,
            notification_type=notification_type,
            title=title[:TITLE_LENGTH],
            message=message,
            course=course,
            sent_by=sent_by)
        for user in unique_recipients.values()
    ]
    Notification.objects.bulk_create(notifications)
    return len(notifications)


def course_student_users(course):
    return User.objects.filter(
        is_active=True,
        student_profile__enrolments__course=course,
        student_profile__enrolments__status=Enrolment.Status.ACTIVE).distinct()


def admin_users():
    return User.objects.filter(role__in=ADMIN_ROLES, is_active=True)


def has_unread_alert(user, title) -> bool:
    return Notification.objects.filter(
        recipient=user,
        title=title[:TITLE_LENGTH],
        notification_type=Notification.Type.ACADEMIC_ALERT,
        is_read=False).exists()