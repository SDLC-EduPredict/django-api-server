import logging

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required, role_required
from accounts.forms import ProfileUpdateForm, with_current_values
from accounts.models import User
from core.responses import error_response, paginated_response, success_response
from courses.models import CourseCategory
from courses.serializers import CourseListSerializer
from courses.views.api_views import published_courses
from permissions.constants import EDIT_OWN_PROFILE, MANAGE_STUDENTS, VIEW_OWN_PROFILE, VIEW_STUDENTS
from permissions.decorators import permission_required
from students.forms import StudentFilterForm, StudentProfileForm
from students.models import StudentProfile
from students.serializers import StudentProfileSerializer

logger = logging.getLogger(__name__)


def get_student_profile(user):
    profile, _ = StudentProfile.objects.select_related("user").get_or_create(user=user)
    return profile


def save_student(request, profile, message):
    user_form = ProfileUpdateForm(with_current_values(profile.user, ProfileUpdateForm, request.data), instance=profile.user)
    profile_form = StudentProfileForm(with_current_values(profile, StudentProfileForm, request.data), request.FILES, instance=profile)

    user_form_ok = user_form.is_valid()
    profile_form_ok = profile_form.is_valid()
    if not (user_form_ok and profile_form_ok):
        return error_response("Profile update failed.", {**user_form.errors, **profile_form.errors})

    user_form.save()
    profile = profile_form.save()
    logger.info("Student %s updated by %s", profile.student_code, request.user.email)
    data = StudentProfileSerializer(profile, context={"request": request}).data
    return success_response(message, {"profile": data})


@api_view(["GET", "PATCH"])
@jwt_required
@role_required(User.Role.STUDENT)
def student_profile_view(request):
    profile = get_student_profile(request.user)

    if request.method == "GET":
        return show_own_profile(request, profile)
    return update_own_profile(request, profile)


@permission_required(VIEW_OWN_PROFILE)
def show_own_profile(request, profile):
    data = StudentProfileSerializer(profile, context={"request": request}).data
    return success_response("Student profile fetched successfully.", {"profile": data})


@permission_required(EDIT_OWN_PROFILE)
def update_own_profile(request, profile):
    return save_student(request, profile, "Student profile updated successfully!")


@api_view(["GET"])
@jwt_required
@role_required(User.Role.STUDENT)
@permission_required(VIEW_OWN_PROFILE)
def student_dashboard_view(request):
    profile = get_student_profile(request.user)
    courses = published_courses()

    return success_response("Student dashboard fetched successfully.", {
        "profile": StudentProfileSerializer(profile, context={"request": request}).data,
        "summary": {
            "profile_completion": profile.profile_completion,
            "email_verified": request.user.email_verified,
            "available_courses": courses.count(),
            "course_categories": CourseCategory.objects.filter(is_active=True).count(),
        },
        "latest_courses": CourseListSerializer(courses[:4], many=True, context={"request": request}).data,
    })


@api_view(["GET"])
@jwt_required
@role_required(User.Role.ADMIN, User.Role.SUPER_ADMIN)
@permission_required(VIEW_STUDENTS)
def admin_student_list(request):
    form = StudentFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid search or filter values.", form.errors)

    filters = form.cleaned_data
    students = StudentProfile.objects.select_related("user").filter(user__role=User.Role.STUDENT)

    for word in filters["search"].split():
        students = students.filter(
            Q(student_code__icontains=word) | Q(user__first_name__icontains=word) | Q(user__last_name__icontains=word)
            | Q(user__email__icontains=word) | Q(user__phone__icontains=word))
    if filters["city"]:
        students = students.filter(city__iexact=filters["city"])
    if filters["gender"]:
        students = students.filter(gender=filters["gender"])
    if filters["is_active"] is not None:
        students = students.filter(user__is_active=filters["is_active"])

    return paginated_response(request, students, StudentProfileSerializer, "Students fetched successfully.")


@api_view(["GET", "PATCH"])
@jwt_required
@role_required(User.Role.ADMIN, User.Role.SUPER_ADMIN)
def admin_student_detail(request, student_id):
    profile = StudentProfile.objects.select_related("user").filter(pk=student_id, user__role=User.Role.STUDENT).first()
    if profile is None:
        return error_response("Student not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return show_student(request, profile)
    return update_student(request, profile)


@permission_required(VIEW_STUDENTS)
def show_student(request, profile):
    data = StudentProfileSerializer(profile, context={"request": request}).data
    return success_response("Student fetched successfully.", {"profile": data})


@permission_required(MANAGE_STUDENTS)
def update_student(request, profile):
    return save_student(request, profile, "Student updated successfully!")