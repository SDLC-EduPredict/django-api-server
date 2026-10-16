import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.db import transaction
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from enrolments.utils import GRADABLE_STATUSES
from ml_prediction.models import MLModelVersion, Prediction
from performance.models import Performance
from performance.serializers import MLDatasetSerializer
from performance.utils import performance_indicator

logger = logging.getLogger(__name__)

FEATURES = Prediction.FEATURES
TARGET = "final_score"
LIMITS = {
    "attendance": (0, 100),
    "assignment_average": (0, 100),
    "mock_test_average": (0, 100),
    "practice_hours": (0, 168),
    "previous_score": (0, 100),
    "modules_completed": (0, 100),
    "final_score": (0, 100),
}
PERFORMANCE_FIELDS = {
    "attendance": "attendance_percentage",
    "assignment_average": "assignment_average",
    "mock_test_average": "mock_test_average",
    "practice_hours": "practice_hours",
    "previous_score": "previous_score",
    "modules_completed": "modules_completed_percentage",
}
MIN_TRAINING_ROWS = 20
MIN_KNOWN_FEATURES = 3
TEST_SIZE = 0.2
RANDOM_STATE = 42
SAMPLE_DATASET = Path(__file__).resolve().parent / "data" / "historical_student_data.csv"

loaded_models = {}


class TrainingError(Exception):
    pass


class ModelNotReady(Exception):
    pass


def model_folder() -> Path:
    folder = Path(settings.ML_MODEL_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def read_csv(file) -> pd.DataFrame:
    try:
        return pd.read_csv(file)
    except FileNotFoundError:
        raise TrainingError(f"File not found: {file}")
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        raise TrainingError("The file is not a valid CSV file.")


def database_dataset() -> pd.DataFrame:
    performances = (Performance.objects
                    .select_related("enrolment__student", "enrolment__course")
                    .filter(enrolment__status__in=GRADABLE_STATUSES, exam_average__isnull=False))
    rows = MLDatasetSerializer(performances, many=True).data
    return pd.DataFrame(rows, columns=list(MLDatasetSerializer.Meta.fields))


def load_dataset(source, file=None) -> tuple[pd.DataFrame, str]:
    if source == MLModelVersion.DataSource.DATABASE:
        return database_dataset(), "Performance records"
    if source == MLModelVersion.DataSource.CSV:
        return read_csv(file), Path(getattr(file, "name", str(file))).name
    return read_csv(SAMPLE_DATASET), SAMPLE_DATASET.name


def clean_dataset(data: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in FEATURES + [TARGET] if column not in data.columns]
    if missing:
        raise TrainingError(f"The dataset is missing these columns: {', '.join(missing)}.")

    data = data[FEATURES + [TARGET]].apply(pd.to_numeric, errors="coerce")
    data = data.dropna(subset=[TARGET]).drop_duplicates()

    for column, (low, high) in LIMITS.items():
        data = data[data[column].isna() | data[column].between(low, high)]

    return data[data[FEATURES].notna().sum(axis=1) >= MIN_KNOWN_FEATURES]


def feature_correlations(data: pd.DataFrame) -> dict:
    correlations = data.corr()[TARGET]
    return {feature: None if pd.isna(correlations[feature]) else round(float(correlations[feature]), 3) for feature in FEATURES}


def next_version_number() -> int:
    last = MLModelVersion.objects.order_by("-version").first()
    return last.version + 1 if last else 1


def train_model(source=MLModelVersion.DataSource.SAMPLE, file=None, user=None) -> MLModelVersion:
    raw_data, source_name = load_dataset(source, file)
    data = clean_dataset(raw_data)
    if len(data) < MIN_TRAINING_ROWS:
        raise TrainingError(f"At least {MIN_TRAINING_ROWS} clean rows with a {TARGET} are needed to train the model. Found {len(data)}.")

    empty_columns = [column for column in FEATURES if data[column].isna().all()]
    if empty_columns:
        raise TrainingError(f"These columns have no values: {', '.join(empty_columns)}.")

    x_train, x_test, y_train, y_test = train_test_split(data[FEATURES], data[TARGET], test_size=TEST_SIZE, random_state=RANDOM_STATE)

    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="mean")),
        ("model", LinearRegression()),
    ])
    pipeline.fit(x_train, y_train)
    test_predictions = pipeline.predict(x_test)
    mse = mean_squared_error(y_test, test_predictions)

    regression = pipeline.named_steps["model"]
    imputer = pipeline.named_steps["imputer"]
    version_number = next_version_number()
    file_name = f"linear_regression_v{version_number}.pkl"
    joblib.dump(pipeline, model_folder() / file_name)

    with transaction.atomic():
        MLModelVersion.objects.filter(is_active=True).update(is_active=False)
        version = MLModelVersion.objects.create(
            version=version_number,
            file_name=file_name,
            data_source=source,
            source_name=source_name,
            features=FEATURES,
            target=TARGET,
            total_rows=len(raw_data),
            cleaned_rows=len(data),
            training_rows=len(x_train),
            test_rows=len(x_test),
            mae=round(float(mean_absolute_error(y_test, test_predictions)), 4),
            mse=round(float(mse), 4),
            rmse=round(float(np.sqrt(mse)), 4),
            r2_score=round(float(r2_score(y_test, test_predictions)), 4),
            intercept=round(float(regression.intercept_), 4),
            coefficients={feature: round(float(value), 4) for feature, value in zip(FEATURES, regression.coef_)},
            feature_means={feature: round(float(value), 2) for feature, value in zip(FEATURES, imputer.statistics_)},
            correlations=feature_correlations(data),
            is_active=True,
            trained_by=user)

    logger.info("ML model %s trained from %s (%s rows), R2=%s", version.name, source_name, len(data), version.r2_score)
    refresh_all_predictions()
    return version


def activate_model(version) -> MLModelVersion:
    load_model(version)
    with transaction.atomic():
        MLModelVersion.objects.filter(is_active=True).update(is_active=False)
        version.is_active = True
        version.save(update_fields=["is_active", "updated_at"])
    refresh_all_predictions()
    return version


def active_model_version():
    return MLModelVersion.objects.filter(is_active=True).first()


def load_model(version):
    if version.id in loaded_models:
        return loaded_models[version.id]

    path = Path(settings.ML_MODEL_DIR) / version.file_name
    if not path.exists():
        raise ModelNotReady(f"The model file {version.file_name} was not found. Train the model again.")
    try:
        pipeline = joblib.load(path)
    except Exception as error:
        logger.exception("Could not load %s", path)
        raise ModelNotReady(f"The model file {version.file_name} could not be loaded. Train the model again.") from error

    loaded_models[version.id] = pipeline
    return pipeline


def predict_score(version, values: dict) -> float:
    row = pd.DataFrame([{feature: values.get(feature) for feature in FEATURES}], columns=FEATURES, dtype=float)
    score = float(load_model(version).predict(row)[0])
    return round(min(max(score, 0), 100), 2)


def performance_features(performance) -> dict:
    values = {feature: getattr(performance, field) for feature, field in PERFORMANCE_FIELDS.items()}
    return {feature: None if value is None else round(float(value), 2) for feature, value in values.items()}


def missing_features(values: dict) -> list[str]:
    return [feature for feature in FEATURES if values.get(feature) is None]


def has_enough_data(values: dict) -> bool:
    return len(FEATURES) - len(missing_features(values)) >= MIN_KNOWN_FEATURES


def refresh_prediction(performance, version):
    values = performance_features(performance)
    if not has_enough_data(values):
        Prediction.objects.filter(enrolment_id=performance.enrolment_id).delete()
        return None

    prediction = getattr(performance.enrolment, "prediction", None)
    if prediction and prediction.model_version_id == version.id and prediction.feature_values() == values:
        return prediction

    score = predict_score(version, values)
    prediction, _ = Prediction.objects.update_or_create(
        enrolment_id=performance.enrolment_id,
        defaults={**values, "model_version": version, "predicted_final_score": score, "indicator": performance_indicator(score)})
    return prediction


def refresh_predictions(performances, version) -> dict:
    return {performance.enrolment_id: refresh_prediction(performance, version) for performance in performances}


def refresh_all_predictions() -> int:
    version = active_model_version()
    if version is None:
        return 0
    performances = (Performance.objects
                    .select_related("enrolment__prediction")
                    .filter(enrolment__status__in=GRADABLE_STATUSES))
    predictions = refresh_predictions(performances, version)
    return len([prediction for prediction in predictions.values() if prediction])