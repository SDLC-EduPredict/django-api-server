import logging

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required, role_required
from accounts.forms import with_current_values
from accounts.models import User
from core.responses import error_response, paginated_response, success_response
from enrolments.forms import EnrolForm, EnrolmentCreateForm, EnrolmentFilterForm, EnrolmentUpdateForm, StudentCourseFilterForm
from enrolments.models import Enrolment
from enrolments.serializers import EnrolmentDetailSerializer, EnrolmentSerializer, StudentEnrolmentSerializer
from enrolments.utils import STAFF_ROLES, staff_enrolments, student_enrolments
from permissions.constants import ENROL_IN_COURSE, MANAGE_ENROLMENTS, VIEW_OWN_ENROLMENTS, VIEW_STUDENTS
from permissions.decorators import permission_required
from students.views.api_views import get_student_profile

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
@jwt_required
@role_required(User.Role.STUDENT)
def student_courses(request):
    if request.method == "GET":
        return list_my_courses(request)
    return enrol_in_course(request)


@permission_required(VIEW_OWN_ENROLMENTS)
def list_my_courses(request):
    form = StudentCourseFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid filter values.", form.errors)

    enrolments = student_enrolments(request.user)
    if form.cleaned_data["course"]:
        enrolments = enrolments.filter(course_id=form.cleaned_data["course"])

    data = StudentEnrolmentSerializer(enrolments, many=True, context={"request": request}).data
    return success_response("Enrolled courses fetched successfully.", {"courses": data})


@permission_required(ENROL_IN_COURSE)
def enrol_in_course(request):
    form = EnrolForm(request.data, student=get_student_profile(request.user))
    if not form.is_valid():
        return error_response("Enrolment failed.", form.errors)

    enrolment = form.save()
    logger.info("%s enrolled in '%s'", request.user.email, enrolment.course.title)
    data = StudentEnrolmentSerializer(enrolment, context={"request": request}).data
    return success_response("Enrolled in the course successfully!", {"enrolment": data}, status.HTTP_201_CREATED)


@api_view(["GET"])
@jwt_required
@role_required(User.Role.STUDENT)
@permission_required(VIEW_OWN_ENROLMENTS)
def student_course_detail(request, enrolment_id):
    enrolment = student_enrolments(request.user).filter(pk=enrolment_id).first()
    if enrolment is None:
        return error_response("Enrolment not found.", status_code=status.HTTP_404_NOT_FOUND)

    data = StudentEnrolmentSerializer(enrolment, context={"request": request}).data
    return success_response("Enrolled course fetched successfully.", {"enrolment": data})


@api_view(["GET", "POST"])
@jwt_required
@role_required(*STAFF_ROLES)
def enrolment_list_create(request):
    if request.method == "GET":
        return list_enrolments(request)
    return create_enrolment(request)


@permission_required(VIEW_STUDENTS)
def list_enrolments(request):
    form = EnrolmentFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid search or filter values.", form.errors)

    filters = form.cleaned_data
    enrolments = staff_enrolments(request.user)

    for word in filters["search"].split():
        enrolments = enrolments.filter(
            Q(student__student_code__icontains=word) | Q(student__user__first_name__icontains=word)
            | Q(student__user__last_name__icontains=word) | Q(student__user__email__icontains=word)
            | Q(course__title__icontains=word))
    if filters["course"]:
        enrolments = enrolments.filter(course_id=filters["course"])
    if filters["status"]:
        enrolments = enrolments.filter(status=filters["status"])

    return paginated_response(request, enrolments, EnrolmentSerializer, "Enrolments fetched successfully.")


@permission_required(MANAGE_ENROLMENTS)
def create_enrolment(request):
    form = EnrolmentCreateForm(request.data)
    if not form.is_valid():
        return error_response("Enrolment creation failed.", form.errors)

    enrolment = form.save()
    logger.info("Enrolment %s created by %s", enrolment, request.user.email)
    return success_response("Enrolment created successfully!", {"enrolment": EnrolmentDetailSerializer(enrolment).data}, status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@jwt_required
@role_required(*STAFF_ROLES)
def enrolment_detail(request, enrolment_id):
    enrolment = staff_enrolments(request.user).filter(pk=enrolment_id).first()
    if enrolment is None:
        return error_response("Enrolment not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return show_enrolment(request, enrolment)
    if request.method == "PATCH":
        return update_enrolment(request, enrolment)
    return delete_enrolment(request, enrolment)


@permission_required(VIEW_STUDENTS)
def show_enrolment(request, enrolment):
    return success_response("Enrolment fetched successfully.", {"enrolment": EnrolmentDetailSerializer(enrolment).data})


@permission_required(MANAGE_ENROLMENTS)
def update_enrolment(request, enrolment):
    form = EnrolmentUpdateForm(with_current_values(enrolment, EnrolmentUpdateForm, request.data), instance=enrolment)
    if not form.is_valid():
        return error_response("Enrolment update failed.", form.errors)

    enrolment = form.save()
    logger.info("Enrolment %s updated by %s", enrolment, request.user.email)
    return success_response("Enrolment updated successfully!", {"enrolment": EnrolmentDetailSerializer(enrolment).data})


@permission_required(MANAGE_ENROLMENTS)
def delete_enrolment(request, enrolment):
    if enrolment.has_academic_records():
        return error_response("This enrolment already has attendance, assignment or assessment records. Set its status to DROPPED instead.")

    enrolment.delete()
    logger.info("Enrolment %s deleted by %s", enrolment, request.user.email)
    return success_response("Enrolment deleted successfully!")
