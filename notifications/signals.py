from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from accounts.models import User
from assessments.models import Assessment, AssessmentResult
from assignments.models import Assignment, AssignmentSubmission
from enrolments.models import Enrolment
from notifications.models import Notification
from notifications.utils import admin_users, course_student_users, has_unread_alert, notify
from performance.models import Performance
from performance.utils import indicator_changed


@receiver(pre_save, sender=User)
def remember_old_user_status(sender, instance, **kwargs):
    instance.old_is_active = User.objects.filter(pk=instance.pk).values_list("is_active", flat=True).first()


@receiver(post_save, sender=User)
def faculty_account_changed(sender, instance, created, **kwargs):
    if instance.role != User.Role.FACULTY:
        return

    if created and not instance.is_active:
        notify(
            admin_users(), Notification.Type.ADMINISTRATIVE, "New faculty registration",
            f"{instance.get_full_name()} ({instance.email}) registered as faculty and is waiting for approval.")
    elif not created and instance.old_is_active is False and instance.is_active:
        notify(
            [instance], Notification.Type.ADMINISTRATIVE, "Faculty account approved",
            "Your faculty account has been approved. You can now manage your courses and students.")


@receiver(pre_save, sender=Enrolment)
def remember_old_enrolment_status(sender, instance, **kwargs):
    instance.old_status = Enrolment.objects.filter(pk=instance.pk).values_list("status", flat=True).first()


@receiver(post_save, sender=Enrolment)
def enrolment_changed(sender, instance, created, **kwargs):
    course = instance.course
    student_user = instance.student.user

    if created:
        notify(
            [student_user], Notification.Type.COURSE, "Enrolment confirmed",
            f"You are enrolled in {course.title}. Your course starts on {instance.start_date}.", course=course)
    elif instance.old_status != instance.status:
        notify(
            [student_user], Notification.Type.COURSE, "Enrolment status updated",
            f"Your enrolment in {course.title} is now {instance.get_status_display()}.", course=course)


@receiver(post_save, sender=Assignment)
def assignment_created(sender, instance, created, **kwargs):
    if not created:
        return

    course = instance.course
    notify(
        course_student_users(course), Notification.Type.ASSIGNMENT, f"New assignment: {instance.title}",
        f"A new assignment '{instance.title}' was added to {course.title}. Due date: {instance.due_date}. Max marks: {instance.max_marks}.",
        course=course, sent_by=instance.created_by)


@receiver(post_save, sender=AssignmentSubmission)
def submission_saved(sender, instance, **kwargs):
    assignment = instance.assignment
    course = assignment.course
    student = instance.enrolment.student

    if instance.status == AssignmentSubmission.Status.GRADED and instance.marks is not None:
        notify(
            [student.user], Notification.Type.ASSIGNMENT, f"Assignment graded: {assignment.title}",
            f"Your assignment '{assignment.title}' in {course.title} was graded: {float(instance.marks):g} / {assignment.max_marks}.",
            course=course, sent_by=instance.graded_by)
    elif instance.status == AssignmentSubmission.Status.SUBMITTED and instance.submitted_at:
        notify(
            [course.faculty], Notification.Type.ASSIGNMENT, f"Assignment submitted: {assignment.title}",
            f"{student.user.get_full_name()} ({student.student_code}) submitted '{assignment.title}' in {course.title}.",
            course=course, sent_by=student.user)


@receiver(post_save, sender=Assessment)
def assessment_created(sender, instance, created, **kwargs):
    if not created:
        return

    course = instance.course
    notify(
        course_student_users(course), Notification.Type.ASSESSMENT,
        f"New {instance.get_assessment_type_display().lower()}: {instance.title}",
        f"{instance.title} for {course.title} is scheduled on {instance.assessment_date}. Max marks: {instance.max_marks}, pass marks: {instance.pass_marks}.",
        course=course, sent_by=instance.created_by)


@receiver(post_save, sender=AssessmentResult)
def result_saved(sender, instance, **kwargs):
    assessment = instance.assessment
    course = assessment.course
    notify(
        [instance.enrolment.student.user], Notification.Type.ASSESSMENT, f"Result published: {assessment.title}",
        f"Your result for {assessment.title} in {course.title}: {float(instance.marks_obtained):g} / {assessment.max_marks} ({instance.result}).",
        course=course, sent_by=instance.entered_by)


@receiver(indicator_changed, sender=Performance)
def performance_needs_attention(sender, performance, old_indicator, **kwargs):
    if performance.indicator != Performance.Indicator.NEEDS_ATTENTION:
        return

    enrolment = performance.enrolment
    course = enrolment.course
    student = enrolment.student

    student_title = f"Academic alert: {course.title}"
    if not has_unread_alert(student.user, student_title):
        notify(
            [student.user], Notification.Type.ACADEMIC_ALERT, student_title,
            f"Your overall score in {course.title} is {float(performance.overall_score):g}. Please talk to your faculty about extra academic support.",
            course=course)

    faculty_title = f"Student needs attention: {student.student_code} in {course.title}"
    if course.faculty and not has_unread_alert(course.faculty, faculty_title):
        notify(
            [course.faculty], Notification.Type.ACADEMIC_ALERT, faculty_title,
            f"{student.user.get_full_name()} ({student.student_code}) has an overall score of {float(performance.overall_score):g} in {course.title}.",
            course=course)