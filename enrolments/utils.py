from accounts.models import User
from courses.models import Course
from enrolments.models import Enrolment

GRADABLE_STATUSES = [Enrolment.Status.ACTIVE, Enrolment.Status.COMPLETED]
STAFF_ROLES = (User.Role.FACULTY, User.Role.ADMIN, User.Role.SUPER_ADMIN)


def staff_courses(user):
    courses = Course.objects.select_related("category", "faculty")
    if user.role == User.Role.FACULTY:
        return courses.filter(faculty=user)
    return courses


def staff_enrolments(user):
    enrolments = Enrolment.objects.select_related("student__user", "course")
    if user.role == User.Role.FACULTY:
        return enrolments.filter(course__faculty=user)
    return enrolments


def student_enrolments(user):
    return Enrolment.objects.select_related("course__category", "course__faculty").filter(student__user=user)


def course_students(course):
    return (Enrolment.objects
            .select_related("student__user")
            .filter(course=course, status__in=GRADABLE_STATUSES)
            .order_by("student__student_code"))


def percentage(value, total):
    if not total:
        return None
    return round(float(value) * 100 / float(total), 2)


def average(values):
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def validate_records(records, make_form):
    if not isinstance(records, list) or not records:
        return [], {"records": ["Send a non-empty list of records."]}

    forms = [make_form(record if isinstance(record, dict) else {}) for record in records]
    errors = {str(index): form.errors for index, form in enumerate(forms) if not form.is_valid()}
    if errors:
        return forms, errors

    enrolment_ids = [form.cleaned_data["enrolment"].pk for form in forms]
    if len(enrolment_ids) != len(set(enrolment_ids)):
        return forms, {"records": ["The same enrolment is sent more than once."]}
    return forms, {}
