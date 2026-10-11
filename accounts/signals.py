from django.db import DatabaseError
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import FacultyProfile, User


@receiver(post_save, sender=User)
def create_faculty_profile(sender, instance, **kwargs):
    if instance.role == User.Role.FACULTY:
        FacultyProfile.objects.get_or_create(user=instance)


def create_missing_faculty_profiles(sender, **kwargs):
    try:
        for user in User.objects.filter(role=User.Role.FACULTY, faculty_profile__isnull=True):
            FacultyProfile.objects.create(user=user)
    except DatabaseError:
        pass