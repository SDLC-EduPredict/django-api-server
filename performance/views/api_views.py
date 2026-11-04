import csv
import logging

from django.db.models import F, Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required, role_required
from accounts.forms import with_current_values
from accounts.models import User
from core.responses import error_response, paginated_response, success_response
from enrolments.forms import StudentCourseFilterForm
from enrolments.serializers import CourseShortSerializer
from enrolments.utils import GRADABLE_STATUSES, STAFF_ROLES, staff_courses
from performance.forms import DatasetFilterForm, PerformanceFilterForm, PerformanceInputForm, PerformanceSummaryForm
from performance.models import Performance
from performance.serializers import MLDatasetSerializer, PerformanceSerializer, StaffPerformanceSerializer
from performance.utils import ML_FEATURES, ML_TARGET, indicator_counts, performance_summary
from permissions.constants import MANAGE_ML_MODEL, MANAGE_PERFORMANCE, VIEW_OWN_PERFORMANCE, VIEW_PERFORMANCE
from permissions.decorators import permission_required

logger = logging.getLogger(__name__)

ORDERINGS = {
    "overall_score": F("overall_score").asc(nulls_last=True),
    "-overall_score": F("overall_score").desc(nulls_last=True),
    "enrolment__student__student_code": F("enrolment__student__student_code").asc(),
}


def all_performances():
    return Performance.objects.select_related("enrolment__student__user", "enrolment__course", "updated_by")


def staff_performances(user):
    performances = all_performances()
    if user.role == User.Role.FACULTY:
        return performances.filter(enrolment__course__faculty=user)
    return performances


def student_performances(user):
    return all_performances().filter(enrolment__student__user=user, enrolment__status__in=GRADABLE_STATUSES)


def student_performance_card(performance) -> dict:
    return {
        "enrolment_id": performance.enrolment_id,
        "course": CourseShortSerializer(performance.enrolment.course).data,
        "performance": PerformanceSerializer(performance).data,
    }


def filter_performances(performances, filters):
    for word in filters["search"].split():
        performances = performances.filter(
            Q(enrolment__student__student_code__icontains=word) | Q(enrolment__student__user__first_name__icontains=word)
            | Q(enrolment__student__user__last_name__icontains=word) | Q(enrolment__student__user__email__icontains=word)
            | Q(enrolment__course__title__icontains=word))
    if filters["course"]:
        performances = performances.filter(enrolment__course_id=filters["course"])
    if filters["enrolment"]:
        performances = performances.filter(enrolment_id=filters["enrolment"])
    if filters["status"]:
        performances = performances.filter(enrolment__status=filters["status"])
    if filters["indicator"]:
        performances = performances.filter(indicator=filters["indicator"])
    if filters["participation"]:
        performances = performances.filter(participation=filters["participation"])
    if filters["ordering"]:
        performances = performances.order_by(ORDERINGS[filters["ordering"]], "id")
    return performances


def csv_response(rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="edu_predict_performance_dataset.csv"'
    writer = csv.DictWriter(response, fieldnames=MLDatasetSerializer.Meta.fields)
    writer.writeheader()
    writer.writerows(rows)
    return response


@api_view(["GET"])
@jwt_required
@role_required(User.Role.STUDENT)
@permission_required(VIEW_OWN_PERFORMANCE)
def student_performance(request):
    form = StudentCourseFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid filter values.", form.errors)

    performances = student_performances(request.user)
    if form.cleaned_data["course"]:
        performances = performances.filter(enrolment__course_id=form.cleaned_data["course"])

    performances = list(performances)
    return success_response("Performance fetched successfully.", {
        "overall": {"courses": len(performances), **performance_summary(performances)},
        "courses": [student_performance_card(performance) for performance in performances],
    })


@api_view(["GET"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(VIEW_PERFORMANCE)
def performance_list(request):
    form = PerformanceFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid search or filter values.", form.errors)

    performances = filter_performances(staff_performances(request.user), form.cleaned_data)
    return paginated_response(request, performances, StaffPerformanceSerializer, "Performance records fetched successfully.")


@api_view(["GET"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(VIEW_PERFORMANCE)
def course_performance_summary(request):
    form = PerformanceSummaryForm(request.query_params, courses=staff_courses(request.user))
    if not form.is_valid():
        return error_response("Invalid course.", form.errors)

    course = form.cleaned_data["course"]
    performances = list(all_performances().filter(enrolment__course=course, enrolment__status__in=GRADABLE_STATUSES))
    return success_response("Course performance summary fetched successfully.", {
        "course": CourseShortSerializer(course).data,
        "summary": {"students": len(performances), **performance_summary(performances), "indicators": indicator_counts(performances)},
        "students": StaffPerformanceSerializer(performances, many=True).data,
    })


@api_view(["GET", "PATCH"])
@jwt_required
@role_required(*STAFF_ROLES)
def performance_detail(request, performance_id):
    performance = staff_performances(request.user).filter(pk=performance_id).first()
    if performance is None:
        return error_response("Performance record not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return show_performance(request, performance)
    return update_performance(request, performance)


@permission_required(VIEW_PERFORMANCE)
def show_performance(request, performance):
    return success_response("Performance record fetched successfully.", {"performance": StaffPerformanceSerializer(performance).data})


@permission_required(MANAGE_PERFORMANCE)
def update_performance(request, performance):
    form = PerformanceInputForm(with_current_values(performance, PerformanceInputForm, request.data), instance=performance, user=request.user)
    if not form.is_valid():
        return error_response("Performance update failed.", form.errors)

    performance = form.save()
    logger.info("Performance of %s updated by %s", performance.enrolment, request.user.email)
    return success_response("Performance updated successfully!", {"performance": StaffPerformanceSerializer(performance).data})


@api_view(["GET"])
@jwt_required
@role_required(User.Role.ADMIN, User.Role.SUPER_ADMIN)
@permission_required(MANAGE_ML_MODEL)
def ml_dataset(request):
    form = DatasetFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid filter values.", form.errors)

    performances = all_performances().filter(enrolment__status__in=GRADABLE_STATUSES).order_by("enrolment_id")
    if form.cleaned_data["course"]:
        performances = performances.filter(enrolment__course_id=form.cleaned_data["course"])

    rows = MLDatasetSerializer(performances, many=True).data
    if form.cleaned_data["export"] == "csv":
        return csv_response(rows)

    return success_response("ML dataset fetched successfully.", {
        "features": ML_FEATURES,
        "target": ML_TARGET,
        "count": len(rows),
        "rows": rows,
    })