from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required, role_required
from accounts.models import User
from accounts.serializers import UserSerializer
from analytics.forms import AttentionReportFilterForm, CourseReportFilterForm, PredictionReportFilterForm
from analytics.serializers import CoursePerformanceSerializer, PendingSubmissionSerializer, StudentProgressSerializer
from analytics.utils import (
    count_by, courses_with_performance, csv_response, gradable_performances, indicator_distribution, needing_attention,
    overview, prediction_report, refresh_predictions_for, refresh_user_predictions)
from assessments.models import Assessment, AssessmentResult
from assessments.serializers import AssessmentSerializer
from assignments.models import Assignment, AssignmentSubmission
from assignments.serializers import AssignmentSerializer
from attendance.models import Attendance
from core.responses import error_response, paginated_response, success_response
from courses.models import Course, CourseCategory
from enrolments.models import Enrolment
from enrolments.serializers import EnrolmentDetailSerializer, EnrolmentSerializer
from enrolments.utils import STAFF_ROLES, staff_courses, staff_enrolments
from ml_prediction.serializers import MLModelVersionShortSerializer, PredictionSerializer, StaffPredictionSerializer
from ml_prediction.services import active_model_version
from ml_prediction.views.api_views import staff_predictions
from notifications.models import Notification
from performance.forms import PerformanceFilterForm
from performance.serializers import PerformanceSerializer
from performance.utils import performance_summary
from performance.views.api_views import filter_performances, staff_performances
from permissions.constants import EXPORT_REPORTS, VIEW_ADMIN_DASHBOARD, VIEW_REPORTS, VIEW_STUDENTS
from permissions.decorators import permission_required
from students.models import StudentProfile
from students.serializers import StudentProfileSerializer

ADMIN_ROLES = (User.Role.ADMIN, User.Role.SUPER_ADMIN)
UPCOMING_DAYS = 14


def pending_submissions(courses):
    return (AssignmentSubmission.objects
            .select_related("assignment__course", "enrolment__student__user")
            .filter(assignment__course__in=courses, status=AssignmentSubmission.Status.SUBMITTED, submitted_at__isnull=False)
            .order_by("submitted_at"))


def upcoming_assessments(courses):
    today = timezone.localdate()
    return (Assessment.objects
            .select_related("course", "created_by")
            .filter(course__in=courses, assessment_date__range=(today, today + timedelta(days=UPCOMING_DAYS)))
            .order_by("assessment_date"))


def assignments_due(courses):
    today = timezone.localdate()
    return (Assignment.objects
            .select_related("course", "created_by")
            .filter(course__in=courses, due_date__range=(today, today + timedelta(days=UPCOMING_DAYS)))
            .order_by("due_date"))


def progress_rows(performances):
    return performances.select_related("enrolment__course__faculty", "enrolment__prediction")


@api_view(["GET"])
@jwt_required
@role_required(*ADMIN_ROLES)
@permission_required(VIEW_ADMIN_DASHBOARD)
def admin_dashboard(request):
    user = request.user
    refresh_user_predictions(user)

    courses = staff_courses(user)
    performances = gradable_performances(user)
    predictions = staff_predictions(user)
    faculty = User.objects.filter(role=User.Role.FACULTY)
    model_version = active_model_version()

    return success_response("Admin dashboard fetched successfully.", {
        "summary": overview(user, courses),
        "people": {
            "active_students": StudentProfile.objects.filter(user__is_active=True).count(),
            "inactive_students": StudentProfile.objects.filter(user__is_active=False).count(),
            "active_faculty": faculty.filter(is_active=True).count(),
            "pending_faculty_approvals": faculty.filter(is_active=False).count(),
            "admins": User.objects.filter(role__in=ADMIN_ROLES, is_active=True).count(),
        },
        "courses": {
            "total": courses.count(),
            **count_by(courses, "status", Course.Status.values),
            "active_categories": CourseCategory.objects.filter(is_active=True).count(),
        },
        "enrolments": count_by(Enrolment.objects.all(), "status", Enrolment.Status.values),
        "academic_records": {
            "attendance_records": Attendance.objects.count(),
            "assignments": Assignment.objects.count(),
            "submissions_to_grade": pending_submissions(courses).count(),
            "assessments": Assessment.objects.count(),
            "upcoming_assessments": upcoming_assessments(courses).count(),
            "assessment_results": AssessmentResult.objects.count(),
        },
        "performance_indicators": indicator_distribution(performances),
        "predictions": prediction_report(predictions),
        "active_model": MLModelVersionShortSerializer(model_version).data if model_version else None,
        "students_needing_attention": StudentProgressSerializer(needing_attention(performances)[:5], many=True).data,
        "latest_predictions": StaffPredictionSerializer(predictions.order_by("-updated_at", "-id")[:10], many=True).data,
        "recent_enrolments": EnrolmentSerializer(Enrolment.objects.select_related("student__user", "course")[:5], many=True).data,
        "pending_faculty": UserSerializer(faculty.filter(is_active=False).order_by("-date_joined")[:5], many=True).data,
    })


@api_view(["GET"])
@jwt_required
@role_required(User.Role.FACULTY)
@permission_required(VIEW_STUDENTS)
def faculty_dashboard(request):
    user = request.user
    refresh_user_predictions(user)

    courses = staff_courses(user)
    performances = gradable_performances(user)
    submissions = pending_submissions(courses)
    assessments = upcoming_assessments(courses)
    assignments = assignments_due(courses)

    return success_response("Faculty dashboard fetched successfully.", {
        "summary": overview(user, courses),
        "work": {
            "submissions_to_grade": submissions.count(),
            "assignments_due_soon": assignments.count(),
            "upcoming_assessments": assessments.count(),
            "attendance_marked_today": Attendance.objects.filter(enrolment__course__in=courses, date=timezone.localdate()).count(),
            "unread_notifications": Notification.objects.filter(recipient=user, is_read=False).count(),
        },
        "courses": CoursePerformanceSerializer(courses_with_performance(courses), many=True).data,
        "performance_indicators": indicator_distribution(performances),
        "predictions": prediction_report(staff_predictions(user)),
        "students_needing_attention": StudentProgressSerializer(needing_attention(performances)[:10], many=True).data,
        "submissions_to_grade": PendingSubmissionSerializer(submissions[:10], many=True).data,
        "upcoming_assessments": AssessmentSerializer(assessments[:5], many=True).data,
        "assignments_due_soon": AssignmentSerializer(assignments[:5], many=True).data,
    })


@api_view(["GET"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(VIEW_STUDENTS)
def my_students(request):
    form = PerformanceFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid search or filter values.", form.errors)

    refresh_user_predictions(request.user)
    performances = filter_performances(progress_rows(staff_performances(request.user)), form.cleaned_data)
    return paginated_response(request, performances, StudentProgressSerializer, "Students fetched successfully.")


@api_view(["GET"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(VIEW_STUDENTS)
def student_report(request, student_id):
    student = StudentProfile.objects.select_related("user").filter(pk=student_id).first()
    enrolments = staff_enrolments(request.user).filter(student_id=student_id)

    if student is None or (request.user.role == User.Role.FACULTY and not enrolments.exists()):
        return error_response("Student not found.", status_code=status.HTTP_404_NOT_FOUND)

    refresh_predictions_for(gradable_performances(request.user).filter(enrolment__student_id=student_id))
    enrolments = enrolments.select_related("performance", "prediction__model_version")

    courses = []
    performances = []
    for enrolment in enrolments:
        performance = getattr(enrolment, "performance", None)
        prediction = getattr(enrolment, "prediction", None)
        if performance and enrolment.status != Enrolment.Status.DROPPED:
            performances.append(performance)
        courses.append({
            **EnrolmentDetailSerializer(enrolment).data,
            "performance": PerformanceSerializer(performance).data if performance else None,
            "prediction": PredictionSerializer(prediction).data if prediction else None,
        })

    return success_response("Student report fetched successfully.", {
        "profile": StudentProfileSerializer(student, context={"request": request}).data,
        "overall": {"courses": len(performances), **performance_summary(performances)},
        "courses": courses,
    })


@api_view(["GET"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(VIEW_REPORTS)
def report_overview(request):
    user = request.user
    refresh_user_predictions(user)
    courses = staff_courses(user)

    return success_response("Report overview fetched successfully.", {
        "overview": overview(user, courses),
        "enrolments": count_by(staff_enrolments(user), "status", Enrolment.Status.values),
        "performance_indicators": indicator_distribution(gradable_performances(user)),
        "predictions": prediction_report(staff_predictions(user)),
    })


@api_view(["GET"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(VIEW_REPORTS)
def course_performance_report(request):
    form = CourseReportFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid search or filter values.", form.errors)

    filters = form.cleaned_data
    refresh_user_predictions(request.user)
    courses = staff_courses(request.user)
    for word in filters["search"].split():
        courses = courses.filter(Q(title__icontains=word) | Q(category__name__icontains=word))
    if filters["category"]:
        courses = courses.filter(category_id=filters["category"])
    if filters["status"]:
        courses = courses.filter(status=filters["status"])

    rows = CoursePerformanceSerializer(courses_with_performance(courses), many=True).data
    if filters["export"] == "csv":
        return export_report(request, "edu_predict_course_performance.csv", rows)
    return success_response("Course performance report fetched successfully.", {"count": len(rows), "courses": rows})


@api_view(["GET"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(VIEW_REPORTS)
def attention_report(request):
    form = AttentionReportFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid search or filter values.", form.errors)

    filters = form.cleaned_data
    refresh_user_predictions(request.user)
    performances = needing_attention(staff_performances(request.user))
    for word in filters["search"].split():
        performances = performances.filter(
            Q(enrolment__student__student_code__icontains=word) | Q(enrolment__student__user__first_name__icontains=word)
            | Q(enrolment__student__user__last_name__icontains=word) | Q(enrolment__course__title__icontains=word))
    if filters["course"]:
        performances = performances.filter(enrolment__course_id=filters["course"])

    if filters["export"] == "csv":
        rows = StudentProgressSerializer(performances, many=True).data
        return export_report(request, "edu_predict_students_needing_attention.csv", rows)
    return paginated_response(request, performances, StudentProgressSerializer, "Students needing attention fetched successfully.")


@permission_required(EXPORT_REPORTS)
def export_report(request, file_name, rows):
    return csv_response(file_name, rows)


@api_view(["GET"])
@jwt_required
@role_required(*STAFF_ROLES)
@permission_required(VIEW_REPORTS)
def prediction_distribution_report(request):
    form = PredictionReportFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid filter values.", form.errors)

    refresh_user_predictions(request.user)
    predictions = staff_predictions(request.user)
    if form.cleaned_data["course"]:
        predictions = predictions.filter(enrolment__course_id=form.cleaned_data["course"])

    model_version = active_model_version()
    return success_response("Prediction distribution fetched successfully.", {
        **prediction_report(predictions),
        "active_model": MLModelVersionShortSerializer(model_version).data if model_version else None,
    })