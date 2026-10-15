from django.core.management.base import BaseCommand
from enrolments.models import Enrolment
from performance.utils import refresh_performance


class Command(BaseCommand):
    help = "Recalculate the performance of every enrolment from its attendance, assignments and assessments."

    def handle(self, *args, **options):
        enrolment_ids = list(Enrolment.objects.values_list("id", flat=True))
        for enrolment_id in enrolment_ids:
            refresh_performance(enrolment_id)
        self.stdout.write(self.style.SUCCESS(f"Performance recalculated for {len(enrolment_ids)} enrolment(s)."))