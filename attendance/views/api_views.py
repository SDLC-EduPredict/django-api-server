import logging

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required, role_required
from accounts.forms import with_current_values
from accounts.models import User
from attendance.forms import AttendanceFilterForm, AttendanceRecordForm, AttendanceSheetForm, AttendanceSummaryForm, AttendanceUpdateForm
from attendance.models import Attendance
from attendance.serializers import AttendanceRecordSerializer, AttendanceSerializer
from attendance.utils import attendance_summary
from core.responses import error_response, paginated_response, success_response
from enrolments.forms import StudentCourseFilterForm
from enrolments.models import Enrolment
from enrolments.serializers import CourseShortSerializer, StudentShortSerializer
from enrolments.utils import GRADABLE_STATUSES, STAFF_ROLES, course_students, staff_courses, staff_enrolments, student_enrolments, validate_records
from permissions.constants import MARK_ATTENDANCE, VIEW_ATTENDANCE, VIEW_OWN_ATTENDANCE
from permissions.decorators import permission_required

logger = logging.getLogger(__name__)


def staff_attendance(user):
    attendance = Attendance.objects.select_related("enrolment__student__user", "enrolment__course", "marked_by")
    if user.role == User.Role.FACULTY:
        return attendance.filter(enrolment__course__faculty=user)
    return attendance


def student_attendance_card(enrolment) -> dict:
    return {
        "enrolment_id": enrolment.id,
        "course": CourseShortSerializer(enrolment.course).data,
        "summary": attendance_summary(enrolment),
        "records": AttendanceRecordSerializer(enrolment.attendance_records.all(), many=True).data,
    }


@api_view(["GET"])
@jwt_required
@role_required(User.Role.STUDENT)
@permission_required(VIEW_OWN_ATTENDANCE)
def student_attendance(request):
    form = StudentCourseFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid filter values.", form.errors)

    enrolments = student_enrolments(request.user).filter(status__in=GRADABLE_STATUSES)
    if form.cleaned_data["course"]:
        enrolments = enrolments.filter(course_id=form.cleaned_data["course"])

    courses = [student_attendance_card(enrolment) for enrolment in enrolments]
    return success_response("Attendance fetched successfully.", {"courses": courses})


@api_view(["GET", "POST"])
@jwt_required
@role_required(*STAFF_ROLES)
def attendance_list_create(request):
    if request.method == "GET":
        return list_attendance(request)
    return record_attendance(request)


@permission_required(VIEW_ATTENDANCE)
def list_attendance(request):
    form = AttendanceFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid search or filter values.", form.errors)

    filters = form.cleaned_data
    attendance = staff_attendance(request.user)

    for word in filters["search"].split():
        attendance = attendance.filter(
            Q(enrolment__student__student_code__icontains=word) | Q(enrolment__student__user__first_name__icontains=word)
            | Q(enrolment__student__user__last_name__icontains=word))
    if filters["course"]:
        attendance = attendance.filter(enrolment__course_id=filters["course"])
    if filters["enrolment"]:
        attendance = attendance.filter(enrolment_id=filters["enrolment"])
    if filters["status"]:
        attendance = attendance.filter(status=filters["status"])
    if filters["date"]:
        attendance = attendance.filter(date=filters["date"])
    if filters["date_from"]:
        attendance = attendance.filter(date__gte=filters["date_from"])
    if filters["date_to"]:
        attendance = attendance.filter(date__lte=filters["date_to"])

    return paginated_response(request, attendance, AttendanceSerializer, "Attendance fetched successfully.")


@permission_required(MARK_ATTENDANCE)
def record_attendance(request):
    sheet = AttendanceSheetForm(request.data)
    if not sheet.is_valid():
        return error_response("Attendance could not be recorded.", sheet.errors)

    date = sheet.cleaned_data["date"]
    enrolments = staff_enrolments(request.user).filter(status=Enrolment.Status.ACTIVE)

    forms, errors = validate_records(
        request.data.get("records"),
        lambda record: AttendanceRecordForm(record, enrolments=enrolments, date=date, user=request.user))
    if errors:
        return error_response("Attendance could not be recorded.", errors)

    with transaction.atomic():
        saved = [form.save() for form in forms]

    logger.info("%s attendance records for %s saved by %s", len(saved), date, request.user.email)
    data = AttendanceSerializer(saved, many=True).data
    return success_response(f"Attendance recorded for {len(saved)} student(s).", {"date": date, "records": data}, status.HTTP_201_CREATED)


@api_view(["GET"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(VIEW_ATTENDANCE)
def attendance_summary_view(request):
    form = AttendanceSummaryForm(request.query_params, courses=staff_courses(request.user))
    if not form.is_valid():
        return error_response("Invalid course.", form.errors)

    course = form.cleaned_data["course"]
    students = [
        {"enrolment_id": enrolment.id, "student": StudentShortSerializer(enrolment.student).data, **attendance_summary(enrolment)}
        for enrolment in course_students(course)
    ]
    return success_response("Attendance summary fetched successfully.", {
        "course": CourseShortSerializer(course).data,
        "students": students,
    })


@api_view(["GET", "PATCH", "DELETE"])
@jwt_required
@role_required(*STAFF_ROLES)
def attendance_detail(request, attendance_id):
    attendance = staff_attendance(request.user).filter(pk=attendance_id).first()
    if attendance is None:
        return error_response("Attendance record not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return show_attendance(request, attendance)
    if request.method == "PATCH":
        return update_attendance(request, attendance)
    return delete_attendance(request, attendance)


@permission_required(VIEW_ATTENDANCE)
def show_attendance(request, attendance):
    return success_response("Attendance record fetched successfully.", {"attendance": AttendanceSerializer(attendance).data})


@permission_required(MARK_ATTENDANCE)
def update_attendance(request, attendance):
    form = AttendanceUpdateForm(with_current_values(attendance, AttendanceUpdateForm, request.data), instance=attendance)
    if not form.is_valid():
        return error_response("Attendance update failed.", form.errors)

    attendance = form.save(commit=False)
    attendance.marked_by = request.user
    attendance.save()
    logger.info("Attendance %s updated by %s", attendance.pk, request.user.email)
    return success_response("Attendance updated successfully!", {"attendance": AttendanceSerializer(attendance).data})


@permission_required(MARK_ATTENDANCE)
def delete_attendance(request, attendance):
    attendance.delete()
    logger.info("Attendance of %s on %s deleted by %s", attendance.enrolment, attendance.date, request.user.email)
    return success_response("Attendance record deleted successfully!")
