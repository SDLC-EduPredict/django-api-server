import logging

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required, role_required
from accounts.forms import with_current_values
from accounts.models import User
from assessments.forms import AssessmentCreateForm, AssessmentFilterForm, AssessmentResultForm, AssessmentUpdateForm, StudentResultFilterForm
from assessments.models import Assessment, AssessmentResult
from assessments.serializers import AssessmentSerializer, ResultSerializer, StudentAssessmentSerializer
from assessments.utils import assessment_summary
from core.responses import error_response, paginated_response, success_response
from enrolments.serializers import CourseShortSerializer, StudentShortSerializer
from enrolments.utils import GRADABLE_STATUSES, STAFF_ROLES, course_students, staff_courses, student_enrolments, validate_records
from permissions.constants import ENTER_MARKS, MANAGE_ASSESSMENTS, VIEW_OWN_RESULTS
from permissions.decorators import permission_required

logger = logging.getLogger(__name__)


def staff_assessments(user):
    return Assessment.objects.select_related("course", "created_by").filter(course__in=staff_courses(user))


def student_result_card(enrolment, assessment_type) -> dict:
    assessments = enrolment.course.assessments.all()
    if assessment_type:
        assessments = assessments.filter(assessment_type=assessment_type)
    return {
        "enrolment_id": enrolment.id,
        "course": CourseShortSerializer(enrolment.course).data,
        "summary": assessment_summary(enrolment),
        "assessments": StudentAssessmentSerializer(assessments, many=True, context={"enrolment": enrolment}).data,
    }


@api_view(["GET"])
@jwt_required
@role_required(User.Role.STUDENT)
@permission_required(VIEW_OWN_RESULTS)
def student_results(request):
    form = StudentResultFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid filter values.", form.errors)

    enrolments = student_enrolments(request.user).filter(status__in=GRADABLE_STATUSES)
    if form.cleaned_data["course"]:
        enrolments = enrolments.filter(course_id=form.cleaned_data["course"])

    courses = [student_result_card(enrolment, form.cleaned_data["assessment_type"]) for enrolment in enrolments]
    return success_response("Results fetched successfully.", {"courses": courses})


@api_view(["GET", "POST"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(MANAGE_ASSESSMENTS)
def assessment_list_create(request):
    if request.method == "GET":
        form = AssessmentFilterForm(request.query_params)
        if not form.is_valid():
            return error_response("Invalid search or filter values.", form.errors)

        filters = form.cleaned_data
        assessments = staff_assessments(request.user)
        if filters["course"]:
            assessments = assessments.filter(course_id=filters["course"])
        if filters["assessment_type"]:
            assessments = assessments.filter(assessment_type=filters["assessment_type"])
        if filters["search"]:
            assessments = assessments.filter(title__icontains=filters["search"])
        return paginated_response(request, assessments, AssessmentSerializer, "Assessments fetched successfully.")

    form = AssessmentCreateForm(request.data, courses=staff_courses(request.user))
    if not form.is_valid():
        return error_response("Assessment creation failed.", form.errors)

    assessment = form.save(commit=False)
    assessment.created_by = request.user
    assessment.save()
    logger.info("Assessment '%s' created by %s", assessment.title, request.user.email)
    return success_response("Assessment created successfully!", {"assessment": AssessmentSerializer(assessment).data}, status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(MANAGE_ASSESSMENTS)
def assessment_detail(request, assessment_id):
    assessment = staff_assessments(request.user).filter(pk=assessment_id).first()
    if assessment is None:
        return error_response("Assessment not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return success_response("Assessment fetched successfully.", {"assessment": AssessmentSerializer(assessment).data})

    if request.method == "PATCH":
        form = AssessmentUpdateForm(with_current_values(assessment, AssessmentUpdateForm, request.data), instance=assessment)
        if not form.is_valid():
            return error_response("Assessment update failed.", form.errors)

        assessment = form.save()
        logger.info("Assessment '%s' updated by %s", assessment.title, request.user.email)
        return success_response("Assessment updated successfully!", {"assessment": AssessmentSerializer(assessment).data})

    if assessment.results.exists():
        return error_response("This assessment already has results, so it cannot be deleted.")

    assessment.delete()
    logger.info("Assessment '%s' deleted by %s", assessment.title, request.user.email)
    return success_response("Assessment deleted successfully!")


@api_view(["GET", "POST"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(ENTER_MARKS)
def assessment_results(request, assessment_id):
    assessment = staff_assessments(request.user).filter(pk=assessment_id).first()
    if assessment is None:
        return error_response("Assessment not found.", status_code=status.HTTP_404_NOT_FOUND)

    enrolments = course_students(assessment.course)

    if request.method == "GET":
        students = []
        for enrolment in enrolments:
            result = assessment.results.filter(enrolment=enrolment).first()
            students.append({
                "enrolment_id": enrolment.id,
                "student": StudentShortSerializer(enrolment.student).data,
                "result": ResultSerializer(result).data if result else None,
            })
        return success_response("Results fetched successfully.", {
            "assessment": AssessmentSerializer(assessment).data,
            "students": students,
        })

    forms, errors = validate_records(
        request.data.get("records"),
        lambda record: AssessmentResultForm(record, assessment=assessment, enrolments=enrolments, user=request.user))
    if errors:
        return error_response("Marks could not be saved.", errors)

    with transaction.atomic():
        saved = [form.save() for form in forms]

    logger.info("%s results for '%s' saved by %s", len(saved), assessment.title, request.user.email)
    return success_response(f"Marks saved for {len(saved)} student(s).", {"results": ResultSerializer(saved, many=True).data})


@api_view(["DELETE"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(ENTER_MARKS)
def result_delete(request, result_id):
    result = AssessmentResult.objects.filter(pk=result_id, assessment__in=staff_assessments(request.user)).first()
    if result is None:
        return error_response("Result not found.", status_code=status.HTTP_404_NOT_FOUND)

    result.delete()
    logger.info("Result of %s for '%s' deleted by %s", result.enrolment, result.assessment.title, request.user.email)
    return success_response("Result deleted successfully!")