from django.db import DatabaseError
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from assessments.models import Assessment, AssessmentResult
from assignments.models import Assignment, AssignmentSubmission
from attendance.models import Attendance
from enrolments.models import Enrolment
from performance.utils import refresh_course_performances, refresh_performance


@receiver(post_save, sender=Enrolment)
def enrolment_saved(sender, instance, **kwargs):
    refresh_performance(instance.id)


@receiver(post_save, sender=Attendance)
@receiver(post_save, sender=AssignmentSubmission)
@receiver(post_save, sender=AssessmentResult)
def academic_record_saved(sender, instance, **kwargs):
    refresh_performance(instance.enrolment_id)


@receiver(post_delete, sender=Attendance)
@receiver(post_delete, sender=AssignmentSubmission)
@receiver(post_delete, sender=AssessmentResult)
def academic_record_deleted(sender, instance, **kwargs):
    refresh_performance(instance.enrolment_id, create=False)


@receiver(post_save, sender=Assignment)
@receiver(post_delete, sender=Assignment)
@receiver(post_save, sender=Assessment)
@receiver(post_delete, sender=Assessment)
def course_work_changed(sender, instance, **kwargs):
    refresh_course_performances(instance.course_id)


def create_missing_performances(sender, **kwargs):
    try:
        for enrolment_id in Enrolment.objects.filter(performance__isnull=True).values_list("id", flat=True):
            refresh_performance(enrolment_id)
    except DatabaseError:
        pass