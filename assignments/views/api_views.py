import logging

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required, role_required
from accounts.forms import with_current_values
from accounts.models import User
from assignments.forms import AssignmentCreateForm, AssignmentFilterForm, AssignmentMarksForm, AssignmentUpdateForm, StudentAssignmentFilterForm, SubmissionForm
from assignments.models import Assignment, AssignmentSubmission
from assignments.serializers import AssignmentSerializer, StudentAssignmentSerializer, SubmissionSerializer
from assignments.utils import assignment_summary, submission_status
from core.responses import error_response, paginated_response, success_response
from enrolments.models import Enrolment
from enrolments.serializers import CourseShortSerializer, StudentShortSerializer
from enrolments.utils import GRADABLE_STATUSES, STAFF_ROLES, course_students, staff_courses, student_enrolments, validate_records
from permissions.constants import GRADE_ASSIGNMENTS, MANAGE_ASSIGNMENTS, SUBMIT_ASSIGNMENTS, VIEW_OWN_ASSIGNMENTS
from permissions.decorators import permission_required

logger = logging.getLogger(__name__)


def staff_assignments(user):
    return Assignment.objects.select_related("course", "created_by").filter(course__in=staff_courses(user))


def student_assignment_card(request, enrolment, status_filter) -> dict:
    context = {"request": request, "enrolment": enrolment}
    assignments = StudentAssignmentSerializer(enrolment.course.assignments.all(), many=True, context=context).data
    if status_filter:
        assignments = [assignment for assignment in assignments if assignment["my_status"] == status_filter]
    return {
        "enrolment_id": enrolment.id,
        "course": CourseShortSerializer(enrolment.course).data,
        "summary": assignment_summary(enrolment),
        "assignments": assignments,
    }


@api_view(["GET"])
@jwt_required
@role_required(User.Role.STUDENT)
@permission_required(VIEW_OWN_ASSIGNMENTS)
def student_assignments(request):
    form = StudentAssignmentFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid filter values.", form.errors)

    enrolments = student_enrolments(request.user).filter(status__in=GRADABLE_STATUSES)
    if form.cleaned_data["course"]:
        enrolments = enrolments.filter(course_id=form.cleaned_data["course"])

    courses = [student_assignment_card(request, enrolment, form.cleaned_data["status"]) for enrolment in enrolments]
    return success_response("Assignments fetched successfully.", {"courses": courses})


@api_view(["POST"])
@jwt_required
@role_required(User.Role.STUDENT)
@permission_required(SUBMIT_ASSIGNMENTS)
def submit_assignment(request, assignment_id):
    assignment = Assignment.objects.select_related("course").filter(pk=assignment_id).first()
    enrolment = None
    if assignment:
        enrolment = student_enrolments(request.user).filter(course=assignment.course, status=Enrolment.Status.ACTIVE).first()

    if enrolment is None:
        return error_response("Assignment not found in your active courses.", status_code=status.HTTP_404_NOT_FOUND)

    submission = AssignmentSubmission.objects.filter(assignment=assignment, enrolment=enrolment).first()
    if submission and submission.status == AssignmentSubmission.Status.GRADED:
        return error_response("This assignment is already graded, so it cannot be submitted again.")

    is_first_submission = submission is None
    if is_first_submission:
        submission = AssignmentSubmission(assignment=assignment, enrolment=enrolment)

    form = SubmissionForm(request.data, request.FILES, instance=submission)
    if not form.is_valid():
        return error_response("Submission failed.", form.errors)

    submission = form.save()
    logger.info("%s submitted assignment '%s'", request.user.email, assignment.title)
    data = SubmissionSerializer(submission, context={"request": request}).data
    if is_first_submission:
        return success_response("Assignment submitted successfully!", {"submission": data}, status.HTTP_201_CREATED)
    return success_response("Assignment re-submitted successfully!", {"submission": data})


@api_view(["GET", "POST"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(MANAGE_ASSIGNMENTS)
def assignment_list_create(request):
    if request.method == "GET":
        form = AssignmentFilterForm(request.query_params)
        if not form.is_valid():
            return error_response("Invalid search or filter values.", form.errors)

        assignments = staff_assignments(request.user)
        if form.cleaned_data["course"]:
            assignments = assignments.filter(course_id=form.cleaned_data["course"])
        if form.cleaned_data["search"]:
            assignments = assignments.filter(title__icontains=form.cleaned_data["search"])
        return paginated_response(request, assignments, AssignmentSerializer, "Assignments fetched successfully.")

    form = AssignmentCreateForm(request.data, courses=staff_courses(request.user))
    if not form.is_valid():
        return error_response("Assignment creation failed.", form.errors)

    assignment = form.save(commit=False)
    assignment.created_by = request.user
    assignment.save()
    logger.info("Assignment '%s' created by %s", assignment.title, request.user.email)
    return success_response("Assignment created successfully!", {"assignment": AssignmentSerializer(assignment).data}, status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(MANAGE_ASSIGNMENTS)
def assignment_detail(request, assignment_id):
    assignment = staff_assignments(request.user).filter(pk=assignment_id).first()
    if assignment is None:
        return error_response("Assignment not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return success_response("Assignment fetched successfully.", {"assignment": AssignmentSerializer(assignment).data})

    if request.method == "PATCH":
        form = AssignmentUpdateForm(with_current_values(assignment, AssignmentUpdateForm, request.data), instance=assignment)
        if not form.is_valid():
            return error_response("Assignment update failed.", form.errors)

        assignment = form.save()
        logger.info("Assignment '%s' updated by %s", assignment.title, request.user.email)
        return success_response("Assignment updated successfully!", {"assignment": AssignmentSerializer(assignment).data})

    if assignment.submissions.exists():
        return error_response("Students have already submitted this assignment or received marks, so it cannot be deleted.")

    assignment.delete()
    logger.info("Assignment '%s' deleted by %s", assignment.title, request.user.email)
    return success_response("Assignment deleted successfully!")


@api_view(["GET", "POST"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(GRADE_ASSIGNMENTS)
def assignment_submissions(request, assignment_id):
    assignment = staff_assignments(request.user).filter(pk=assignment_id).first()
    if assignment is None:
        return error_response("Assignment not found.", status_code=status.HTTP_404_NOT_FOUND)

    enrolments = course_students(assignment.course)

    if request.method == "GET":
        students = []
        for enrolment in enrolments:
            submission = assignment.submissions.filter(enrolment=enrolment).first()
            students.append({
                "enrolment_id": enrolment.id,
                "student": StudentShortSerializer(enrolment.student).data,
                "status": submission_status(assignment, submission),
                "submission": SubmissionSerializer(submission, context={"request": request}).data if submission else None,
            })
        return success_response("Submissions fetched successfully.", {
            "assignment": AssignmentSerializer(assignment).data,
            "students": students,
        })

    forms, errors = validate_records(
        request.data.get("records"),
        lambda record: AssignmentMarksForm(record, assignment=assignment, enrolments=enrolments, user=request.user))
    if errors:
        return error_response("Marks could not be saved.", errors)

    with transaction.atomic():
        saved = [form.save() for form in forms]

    logger.info("%s assignment marks for '%s' saved by %s", len(saved), assignment.title, request.user.email)
    data = SubmissionSerializer(saved, many=True, context={"request": request}).data
    return success_response(f"Marks saved for {len(saved)} student(s).", {"submissions": data})