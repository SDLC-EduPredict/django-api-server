import csv

from django.db.models import Avg, Count, Max, Min, Q
from django.http import HttpResponse

from accounts.models import User
from enrolments.models import Enrolment
from enrolments.utils import GRADABLE_STATUSES, staff_enrolments
from ml_prediction.services import ModelNotReady, active_model_version, refresh_predictions
from ml_prediction.views.api_views import staff_predictions
from performance.models import Performance
from performance.utils import AVERAGE_SCORE
from performance.views.api_views import staff_performances
from students.models import StudentProfile

LOW_ATTENDANCE = 75
SCORE_BANDS = [(0, 40, "0-40"), (40, 60, "40-60"), (60, 75, "60-75"), (75, 90, "75-90"), (90, 101, "90-100")]
GRADABLE = Q(enrolments__status__in=GRADABLE_STATUSES)


def rounded(value):
    if value is None:
        return None
    return round(float(value), 2)


def gradable_performances(user):
    return staff_performances(user).filter(enrolment__status__in=GRADABLE_STATUSES)


def refresh_predictions_for(performances) -> None:
    version = active_model_version()
    if version is None:
        return
    try:
        refresh_predictions(performances.select_related("enrolment__prediction"), version)
    except ModelNotReady:
        pass


def refresh_user_predictions(user) -> None:
    refresh_predictions_for(gradable_performances(user))


def performance_averages(performances) -> dict:
    values = performances.aggregate(
        attendance=Avg("attendance_percentage"),
        assignment=Avg("assignment_average"),
        assessment=Avg("assessment_average"),
        overall=Avg("overall_score"))
    return {
        "average_attendance": rounded(values["attendance"]),
        "average_assignment_score": rounded(values["assignment"]),
        "average_assessment_score": rounded(values["assessment"]),
        "average_performance": rounded(values["overall"]),
    }


def count_by(queryset, field, values) -> dict:
    rows = queryset.order_by().values(field).annotate(total=Count("id"))
    counts = {row[field]: row["total"] for row in rows}
    return {value: counts.get(value, 0) for value in values}


def indicator_distribution(queryset) -> dict:
    return count_by(queryset, "indicator", Performance.Indicator.values)


def score_bands(predictions) -> list[dict]:
    return [
        {"band": label, "count": predictions.filter(predicted_final_score__gte=low, predicted_final_score__lt=high).count()}
        for low, high, label in SCORE_BANDS
    ]


def prediction_statistics(predictions) -> dict:
    values = predictions.aggregate(
        total=Count("id"),
        average=Avg("predicted_final_score"),
        lowest=Min("predicted_final_score"),
        highest=Max("predicted_final_score"))
    return {
        "total_predictions": values["total"],
        "average_predicted_score": rounded(values["average"]),
        "lowest_predicted_score": rounded(values["lowest"]),
        "highest_predicted_score": rounded(values["highest"]),
    }


def needing_attention(performances):
    weak = Q(indicator=Performance.Indicator.NEEDS_ATTENTION) | Q(enrolment__prediction__indicator=Performance.Indicator.NEEDS_ATTENTION)
    return (performances
            .select_related("enrolment__course__faculty", "enrolment__prediction")
            .filter(weak, enrolment__status=Enrolment.Status.ACTIVE)
            .order_by("overall_score", "id"))


def attention_reasons(performance) -> list[str]:
    prediction = getattr(performance.enrolment, "prediction", None)
    predicted_score = prediction.predicted_final_score if prediction else None
    checks = [
        (performance.attendance_percentage, LOW_ATTENDANCE, f"Attendance is below {LOW_ATTENDANCE}%"),
        (performance.assignment_average, AVERAGE_SCORE, f"Assignment average is below {AVERAGE_SCORE}"),
        (performance.assessment_average, AVERAGE_SCORE, f"Assessment average is below {AVERAGE_SCORE}"),
        (performance.overall_score, AVERAGE_SCORE, f"Overall score is below {AVERAGE_SCORE}"),
        (predicted_score, AVERAGE_SCORE, f"Predicted final score is below {AVERAGE_SCORE}"),
    ]
    return [message for value, limit, message in checks if value is not None and float(value) < limit]


def student_count(user) -> int:
    if user.role == User.Role.FACULTY:
        return staff_enrolments(user).filter(status__in=GRADABLE_STATUSES).values("student").distinct().count()
    return StudentProfile.objects.filter(user__is_active=True).count()


def overview(user, courses) -> dict:
    performances = gradable_performances(user)
    predictions = staff_predictions(user)
    attention = needing_attention(performances)
    return {
        "total_students": student_count(user),
        "total_courses": courses.count(),
        "active_enrolments": staff_enrolments(user).filter(status=Enrolment.Status.ACTIVE).count(),
        **performance_averages(performances),
        "average_predicted_score": prediction_statistics(predictions)["average_predicted_score"],
        "students_needing_attention": attention.values("enrolment__student").distinct().count(),
        "enrolments_needing_attention": attention.count(),
    }


def prediction_report(predictions) -> dict:
    return {
        **prediction_statistics(predictions),
        "indicators": indicator_distribution(predictions),
        "score_bands": score_bands(predictions),
    }


def courses_with_performance(courses):
    def indicator_count(indicator):
        return Count("enrolments", filter=GRADABLE & Q(enrolments__performance__indicator=indicator))

    return courses.annotate(
        students=Count("enrolments", filter=GRADABLE),
        average_attendance=Avg("enrolments__performance__attendance_percentage", filter=GRADABLE),
        average_assignment_score=Avg("enrolments__performance__assignment_average", filter=GRADABLE),
        average_assessment_score=Avg("enrolments__performance__assessment_average", filter=GRADABLE),
        average_performance=Avg("enrolments__performance__overall_score", filter=GRADABLE),
        average_predicted_score=Avg("enrolments__prediction__predicted_final_score", filter=GRADABLE),
        low_attendance_students=Count("enrolments", filter=GRADABLE & Q(enrolments__performance__attendance_percentage__lt=LOW_ATTENDANCE)),
        good=indicator_count(Performance.Indicator.GOOD),
        average=indicator_count(Performance.Indicator.AVERAGE),
        needs_attention=indicator_count(Performance.Indicator.NEEDS_ATTENTION),
        no_data=indicator_count(Performance.Indicator.NO_DATA)).order_by("title")


def csv_response(file_name, rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    if not rows:
        return response

    writer = csv.DictWriter(response, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: "; ".join(value) if isinstance(value, list) else value for key, value in row.items()})
    return response