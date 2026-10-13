from django.db import DatabaseError
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import User
from students.models import StudentProfile


@receiver(post_save, sender=User)
def create_student_profile(sender, instance, **kwargs):
    if instance.role == User.Role.STUDENT:
        StudentProfile.objects.get_or_create(user=instance)


def create_missing_student_profiles(sender, **kwargs):
    try:
        for user in User.objects.filter(role=User.Role.STUDENT, student_profile__isnull=True):
            StudentProfile.objects.create(user=user)
    except DatabaseError:
        pass