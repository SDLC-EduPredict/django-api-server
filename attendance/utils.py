from attendance.models import Attendance
from enrolments.utils import percentage


def attendance_summary(enrolment) -> dict:
    records = enrolment.attendance_records.all()
    counts = {status: records.filter(status=status).count() for status in Attendance.Status.values}
    total = sum(counts.values())
    attended = counts[Attendance.Status.PRESENT] + counts[Attendance.Status.LATE]
    return {
        "total_classes": total,
        "present": counts[Attendance.Status.PRESENT],
        "late": counts[Attendance.Status.LATE],
        "absent": counts[Attendance.Status.ABSENT],
        "attendance_percentage": percentage(attended, total),
    }