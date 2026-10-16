from django.core.management.base import BaseCommand, CommandError
from ml_prediction.models import MLModelVersion
from ml_prediction.services import TrainingError, train_model


class Command(BaseCommand):
    help = "Train the Linear Regression model (pandas -> cleaning -> train/test split -> evaluation -> save) and make it active."

    def add_arguments(self, parser):
        parser.add_argument("--file", help="Path of a CSV file with the historical student data")
        parser.add_argument("--database", action="store_true", help="Use the performance records of the database (exam average is the final score)")

    def handle(self, *args, **options):
        source = MLModelVersion.DataSource.SAMPLE
        if options["file"]:
            source = MLModelVersion.DataSource.CSV
        if options["database"]:
            source = MLModelVersion.DataSource.DATABASE

        try:
            version = train_model(source, options["file"])
        except TrainingError as error:
            raise CommandError(str(error))

        self.stdout.write(f"Dataset: {version.source_name} ({version.total_rows} rows, {version.cleaned_rows} after cleaning)")
        self.stdout.write(f"Train/Test split: {version.training_rows} / {version.test_rows}")
        self.stdout.write(f"MAE={version.mae}  MSE={version.mse}  RMSE={version.rmse}  R2={version.r2_score}")
        for feature, coefficient in version.coefficients.items():
            self.stdout.write(f"  {feature:<20} coefficient={coefficient:<9} correlation={version.correlations[feature]}")
        self.stdout.write(self.style.SUCCESS(f"Model {version.name} saved as {version.file_name} and activated."))