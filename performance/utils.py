from django.dispatch import Signal
from django.utils import timezone
from assessments.utils import assessment_summary
from assignments.utils import assignment_summary
from attendance.utils import attendance_summary
from enrolments.models import Enrolment
from enrolments.utils import average, percentage
from performance.models import Performance

GOOD_SCORE = 75
AVERAGE_SCORE = 60

OVERALL_SCORE_FIELDS = ["attendance_percentage", "assignment_average", "assessment_average", "modules_completed_percentage"]

SUMMARY_FIELDS = [
    "attendance_percentage", "assignment_average", "mock_test_average", "exam_average", "assessment_average",
    "practice_hours", "previous_score", "modules_completed_percentage", "overall_score",
]

ML_FEATURES = ["attendance", "assignment_average", "mock_test_average", "practice_hours", "previous_score", "modules_completed", "participation"]
ML_TARGET = "final_score"

indicator_changed = Signal()


def performance_indicator(score):
    if score is None:
        return Performance.Indicator.NO_DATA
    if score >= GOOD_SCORE:
        return Performance.Indicator.GOOD
    if score >= AVERAGE_SCORE:
        return Performance.Indicator.AVERAGE
    return Performance.Indicator.NEEDS_ATTENTION


def known_values(performances, field) -> list[float]:
    values = [getattr(performance, field) for performance in performances]
    return [float(value) for value in values if value is not None]


def calculate_performance(performance):
    enrolment = performance.enrolment
    attendance = attendance_summary(enrolment)
    assignments = assignment_summary(enrolment)
    assessments = assessment_summary(enrolment)

    performance.attendance_percentage = attendance["attendance_percentage"]
    performance.assignment_average = assignments["assignment_average"]
    performance.mock_test_average = assessments["mock_test_average"]
    performance.exam_average = assessments["exam_average"]
    performance.assessment_average = assessments["assessment_average"]

    performance.modules_completed_percentage = None
    if performance.modules_completed is not None:
        performance.modules_completed_percentage = percentage(performance.modules_completed, enrolment.course.total_modules)

    scores = [getattr(performance, field) for field in OVERALL_SCORE_FIELDS]
    performance.overall_score = average([float(score) for score in scores if score is not None])
    performance.indicator = performance_indicator(performance.overall_score)
    performance.calculated_at = timezone.now()
    return performance


def refresh_performance(enrolment_id, create=True):
    performance = Performance.objects.select_related("enrolment__course").filter(enrolment_id=enrolment_id).first()

    if performance is None and not create:
        return None

    if performance is None:
        performance = calculate_performance(Performance(enrolment_id=enrolment_id))
        performance.save()
        return performance

    old_indicator = performance.indicator
    calculate_performance(performance)
    values = {field: getattr(performance, field) for field in Performance.CALCULATED_FIELDS}
    Performance.objects.filter(pk=performance.pk).update(**values)
    send_indicator_changed(performance, old_indicator)
    return performance


def send_indicator_changed(performance, old_indicator) -> None:
    if performance.indicator != old_indicator:
        indicator_changed.send(sender=Performance, performance=performance, old_indicator=old_indicator)


def refresh_course_performances(course_id) -> None:
    for enrolment_id in Enrolment.objects.filter(course_id=course_id).values_list("id", flat=True):
        refresh_performance(enrolment_id, create=False)


def performance_summary(performances) -> dict:
    summary = {field: average(known_values(performances, field)) for field in SUMMARY_FIELDS}
    summary["indicator"] = performance_indicator(summary["overall_score"])
    summary["indicator_display"] = Performance.Indicator(summary["indicator"]).label
    return summary


def indicator_counts(performances) -> dict:
    return {indicator: len([item for item in performances if item.indicator == indicator]) for indicator in Performance.Indicator.values}