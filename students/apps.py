from django.apps import AppConfig
from django.db.models.signals import post_migrate


class StudentsConfig(AppConfig):
    name = "students"

    def ready(self):
        from students import signals
        post_migrate.connect(signals.create_missing_student_profiles, sender=self)