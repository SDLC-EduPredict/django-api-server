from django.utils import timezone
from assignments.models import Assignment, AssignmentSubmission
from enrolments.utils import average


def submission_status(assignment, submission) -> str:
    if submission:
        return submission.status
    if assignment.due_date < timezone.localdate():
        return "OVERDUE"
    return "PENDING"


def assignment_summary(enrolment) -> dict:
    total = Assignment.objects.filter(course=enrolment.course).count()
    submissions = enrolment.submissions.select_related("assignment")
    graded = [submission for submission in submissions if submission.status == AssignmentSubmission.Status.GRADED]
    return {
        "total_assignments": total,
        "submitted": len(submissions),
        "graded": len(graded),
        "not_submitted": total - len(submissions),
        "assignment_average": average([submission.percentage for submission in graded]),
    }