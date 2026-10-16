from django.core.management.base import BaseCommand, CommandError
from ml_prediction.services import ModelNotReady, active_model_version, refresh_all_predictions


class Command(BaseCommand):
    help = "Predict the final score of every active or completed enrolment again with the active model."

    def handle(self, *args, **options):
        if active_model_version() is None:
            raise CommandError("No active model. Run: python manage.py train_model")
        try:
            count = refresh_all_predictions()
        except ModelNotReady as error:
            raise CommandError(str(error))
        self.stdout.write(self.style.SUCCESS(f"{count} prediction(s) are up to date."))