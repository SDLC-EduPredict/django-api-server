from django.apps import AppConfig
from django.db.models.signals import post_migrate


class PerformanceConfig(AppConfig):
    name = "performance"

    def ready(self):
        from performance import signals
        post_migrate.connect(signals.create_missing_performances, sender=self)