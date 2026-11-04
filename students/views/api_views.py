import logging

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required, role_required
from accounts.forms import AccountCreateForm, AccountUpdateForm, ProfileUpdateForm, with_current_values
from accounts.models import User
from accounts.tokens import revoke_all_refresh_tokens
from core.responses import error_response, paginated_response, success_response
from courses.models import CourseCategory
from courses.serializers import CourseListSerializer
from courses.views.api_views import published_courses
from enrolments.models import Enrolment
from performance.utils import performance_summary
from performance.views.api_views import student_performances
from permissions.constants import EDIT_OWN_PROFILE, MANAGE_STUDENTS, VIEW_OWN_PROFILE, VIEW_STUDENTS
from permissions.decorators import permission_required
from students.forms import StudentFilterForm, StudentProfileForm
from students.models import StudentProfile
from students.serializers import StudentProfileSerializer

logger = logging.getLogger(__name__)


def get_student_profile(user):
    profile, _ = StudentProfile.objects.select_related("user").get_or_create(user=user)
    return profile


def save_student(request, profile, message, user_form_class=ProfileUpdateForm):
    user_form = user_form_class(with_current_values(profile.user, user_form_class, request.data), instance=profile.user)
    profile_form = StudentProfileForm(with_current_values(profile, StudentProfileForm, request.data), request.FILES, instance=profile)

    user_form_ok = user_form.is_valid()
    profile_form_ok = profile_form.is_valid()
    if not (user_form_ok and profile_form_ok):
        return error_response("Profile update failed.", {**user_form.errors, **profile_form.errors})

    user = user_form.save()
    profile = profile_form.save()
    if not user.is_active:
        revoke_all_refresh_tokens(user)
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
    performances = list(student_performances(request.user))

    return success_response("Student dashboard fetched successfully.", {
        "profile": StudentProfileSerializer(profile, context={"request": request}).data,
        "summary": {
            "profile_completion": profile.profile_completion,
            "email_verified": request.user.email_verified,
            "available_courses": courses.count(),
            "enrolled_courses": profile.enrolments.filter(status=Enrolment.Status.ACTIVE).count(),
            "completed_courses": profile.enrolments.filter(status=Enrolment.Status.COMPLETED).count(),
            "course_categories": CourseCategory.objects.filter(is_active=True).count(),
        },
        "performance": {"courses": len(performances), **performance_summary(performances)},
        "latest_courses": CourseListSerializer(courses[:4], many=True, context={"request": request}).data,
    })


@api_view(["GET", "POST"])
@jwt_required
@role_required(User.Role.ADMIN, User.Role.SUPER_ADMIN)
def admin_student_list(request):
    if request.method == "GET":
        return list_students(request)
    return create_student(request)


@permission_required(VIEW_STUDENTS)
def list_students(request):
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


@permission_required(MANAGE_STUDENTS)
def create_student(request):
    account_form = AccountCreateForm(request.data)
    profile_form = StudentProfileForm(request.data, request.FILES)
    account_form_ok = account_form.is_valid()
    profile_form_ok = profile_form.is_valid()
    if not (account_form_ok and profile_form_ok):
        return error_response("Student creation failed.", {**account_form.errors, **profile_form.errors})

    with transaction.atomic():
        user = account_form.save(User.Role.STUDENT)
        profile_form = StudentProfileForm(request.data, request.FILES, instance=get_student_profile(user))
        if profile_form.is_valid():
            profile_form.save()

    profile = get_student_profile(user)
    logger.info("Student %s created by %s", profile.student_code, request.user.email)
    data = StudentProfileSerializer(profile, context={"request": request}).data
    return success_response("Student created successfully!", {"profile": data}, status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@jwt_required
@role_required(User.Role.ADMIN, User.Role.SUPER_ADMIN)
def admin_student_detail(request, student_id):
    profile = StudentProfile.objects.select_related("user").filter(pk=student_id, user__role=User.Role.STUDENT).first()
    if profile is None:
        return error_response("Student not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return show_student(request, profile)
    if request.method == "PATCH":
        return update_student(request, profile)
    return deactivate_student(request, profile)


@permission_required(VIEW_STUDENTS)
def show_student(request, profile):
    data = StudentProfileSerializer(profile, context={"request": request}).data
    return success_response("Student fetched successfully.", {"profile": data})


@permission_required(MANAGE_STUDENTS)
def update_student(request, profile):
    return save_student(request, profile, "Student updated successfully!", AccountUpdateForm)


@permission_required(MANAGE_STUDENTS)
def deactivate_student(request, profile):
    user = profile.user
    user.is_active = False
    user.save(update_fields=["is_active"])
    revoke_all_refresh_tokens(user)
    logger.info("Student %s deactivated by %s", profile.student_code, request.user.email)
    return success_response("Student deactivated successfully!")