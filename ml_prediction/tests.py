import shutil
import tempfile
from datetime import timedelta
from io import StringIO

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings

from attendance.models import Attendance
from ml_prediction import services
from ml_prediction.models import MLModelVersion, Prediction
from performance.models import Performance
from performance.tests import TODAY, PerformanceTestData

MODEL_DIR = tempfile.mkdtemp()
RAHUL_FEATURES = {"attendance": 88, "assignment_average": 84, "mock_test_average": 78, "practice_hours": 10, "previous_score": 80, "modules_completed": 90}


def tearDownModule():
    shutil.rmtree(MODEL_DIR, ignore_errors=True)


@override_settings(ML_MODEL_DIR=MODEL_DIR)
class MLTestData(PerformanceTestData):
    def setUp(self) -> None:
        super().setUp()
        services.loaded_models.clear()

    def train(self) -> MLModelVersion:
        return services.train_model()

    def complete_rahul(self) -> None:
        self.build_rahul_example()
        performance = self.performance_of(self.rahul)
        self.act_as(self.faculty)
        data = {"practice_hours": 10, "previous_score": 80, "modules_completed": 9, "participation": "HIGH"}
        self.client.patch(f"/api/performance/{performance.id}/", data, format="json")


class TrainingTests(MLTestData):
    def test_sample_dataset_is_cleaned_and_trained(self) -> None:
        version = self.train()
        self.assertEqual((version.name, version.is_active, version.total_rows, version.cleaned_rows), ("v1", True, 505, 495))
        self.assertEqual(version.training_rows + version.test_rows, 495)
        self.assertGreater(version.r2_score, 0.8)
        self.assertEqual(list(version.coefficients), services.FEATURES)
        self.assertTrue((services.model_folder() / version.file_name).exists())

    def test_cleaning_removes_bad_rows(self) -> None:
        good = {**RAHUL_FEATURES, "final_score": 83}
        data = pd.DataFrame([
            good, good,
            {**good, "attendance": 140},
            {**good, "final_score": None},
            {**good, "mock_test_average": "absent"},
            {"attendance": 70, "final_score": 60},
        ])
        cleaned = services.clean_dataset(data)
        self.assertEqual(len(cleaned), 2)
        self.assertTrue(pd.isna(cleaned.iloc[1]["mock_test_average"]))

    def test_dataset_must_have_the_columns_and_enough_rows(self) -> None:
        with self.assertRaisesMessage(services.TrainingError, "missing these columns"):
            services.clean_dataset(pd.DataFrame([{"attendance": 1}]))
        with self.assertRaisesMessage(services.TrainingError, "At least 20 clean rows"):
            services.train_model(MLModelVersion.DataSource.DATABASE)

    def test_retrain_and_activate_an_older_version(self) -> None:
        first = self.train()
        second = self.train()
        first.refresh_from_db()
        self.assertEqual((first.is_active, second.is_active, second.version), (False, True, 2))

        self.act_as(self.admin)
        response = self.client.post(f"/api/ml/models/{first.id}/activate/")
        self.assertEqual(response.status_code, 200, response.json())
        data = self.client.get("/api/ml/models/").json()["data"]
        self.assertEqual((data["active_model"]["name"], len(data["models"])), ("v1", 2))
        self.assertEqual(self.client.post("/api/ml/models/999/activate/").status_code, 404)

    def test_missing_model_file_is_reported(self) -> None:
        version = self.train()
        (services.model_folder() / version.file_name).unlink()
        services.loaded_models.clear()
        self.act_as(self.admin)
        response = self.client.post("/api/ml/predict/", RAHUL_FEATURES, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Train the model again", response.json()["message"])

    def test_train_api_with_csv_upload(self) -> None:
        self.act_as(self.admin)
        csv_file = SimpleUploadedFile("history.csv", services.SAMPLE_DATASET.read_bytes(), content_type="text/csv")
        response = self.client.post("/api/ml/train/", {"file": csv_file}, format="multipart")
        self.assertEqual(response.status_code, 201, response.json())
        model = response.json()["data"]["model"]
        self.assertEqual((model["data_source"], model["source_name"], model["is_active"]), ("CSV", "history.csv", True))

    def test_train_api_rejects_bad_input(self) -> None:
        self.act_as(self.admin)
        self.assertEqual(set(self.client.post("/api/ml/train/", {"source": "CSV"}, format="multipart").json()["errors"]), {"file"})
        text_file = SimpleUploadedFile("notes.txt", b"hello")
        self.assertEqual(set(self.client.post("/api/ml/train/", {"file": text_file}, format="multipart").json()["errors"]), {"file"})
        response = self.client.post("/api/ml/train/", {"source": "DATABASE"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("At least 20 clean rows", response.json()["errors"]["dataset"][0])

    def test_management_commands(self) -> None:
        output = StringIO()
        call_command("train_model", stdout=output)
        self.assertIn("Model v1 saved", output.getvalue())
        self.complete_rahul()
        Prediction.objects.all().delete()
        output = StringIO()
        call_command("refresh_predictions", stdout=output)
        self.assertIn("1 prediction(s)", output.getvalue())

    def test_only_admins_manage_the_model(self) -> None:
        for user in (self.student, self.faculty):
            self.act_as(user)
            self.assertEqual(self.client.post("/api/ml/train/").status_code, 403)
            self.assertEqual(self.client.get("/api/ml/models/").status_code, 403)


class PredictApiTests(MLTestData):
    def test_no_model_yet(self) -> None:
        self.act_as(self.admin)
        response = self.client.post("/api/ml/predict/", RAHUL_FEATURES, format="json")
        self.assertEqual(response.status_code, 503)

    def test_report_example(self) -> None:
        self.train()
        self.act_as(self.admin)
        response = self.client.post("/api/ml/predict/", RAHUL_FEATURES, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()["data"]
        self.assertAlmostEqual(data["predicted_final_score"], 83.7, delta=2)
        self.assertEqual((data["indicator"], data["model_version"]["name"]), ("GOOD", "v1"))
        self.assertEqual(Prediction.objects.count(), 0)

    def test_invalid_input(self) -> None:
        self.train()
        self.act_as(self.admin)
        response = self.client.post("/api/ml/predict/", {**RAHUL_FEATURES, "attendance": 120, "practice_hours": -1, "previous_score": "abc", "modules_completed": None}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()["errors"]), {"attendance", "practice_hours", "previous_score", "modules_completed"})

    def test_predict_for_an_enrolment_is_saved(self) -> None:
        self.train()
        self.complete_rahul()
        self.act_as(self.admin)
        response = self.client.post("/api/ml/predict/", {"enrolment": self.rahul.id}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()["data"]
        self.assertEqual((data["features"], data["missing_features"]), ({key: float(value) for key, value in RAHUL_FEATURES.items()}, []))
        self.assertEqual(Prediction.objects.get(enrolment=self.rahul).indicator, "GOOD")

    def test_not_enough_data_for_an_enrolment(self) -> None:
        self.train()
        self.act_as(self.admin)
        response = self.client.post("/api/ml/predict/", {"enrolment": self.priya.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(response.json()["errors"]["missing_features"]), 6)
        self.assertEqual(self.client.post("/api/ml/predict/", {"enrolment": 99999}, format="json").status_code, 400)

    def test_only_admins_can_run_predictions(self) -> None:
        self.train()
        for user in (self.student, self.faculty):
            self.act_as(user)
            self.assertEqual(self.client.post("/api/ml/predict/", RAHUL_FEATURES, format="json").status_code, 403)


class ViewPredictionTests(MLTestData):
    def setUp(self) -> None:
        super().setUp()
        self.train()
        self.complete_rahul()

    def test_student_sees_own_prediction(self) -> None:
        self.act_as(self.student)
        response = self.client.get("/api/student/prediction/")
        self.assertEqual(response.status_code, 200, response.json())
        course = response.json()["data"]["courses"][0]
        self.assertEqual((course["course"]["title"], course["prediction"]["indicator"]), ("Python Programming", "GOOD"))

    def test_prediction_follows_new_academic_data(self) -> None:
        self.act_as(self.student)
        before = self.client.get("/api/student/prediction/").json()["data"]["courses"][0]["prediction"]
        for days in range(30, 40):
            Attendance.objects.create(enrolment=self.rahul, date=TODAY - timedelta(days=days), status="ABSENT")
        after = self.client.get("/api/student/prediction/").json()["data"]["courses"][0]["prediction"]
        self.assertEqual(before["id"], after["id"])
        self.assertLess(after["attendance"], before["attendance"])
        self.assertLess(after["predicted_final_score"], before["predicted_final_score"])

    def test_student_without_data_gets_no_prediction(self) -> None:
        self.act_as(self.classmate)
        course = self.client.get("/api/student/prediction/").json()["data"]["courses"][0]
        self.assertIsNone(course["prediction"])
        self.assertEqual(len(course["missing_features"]), 6)

    def test_faculty_sees_only_own_students(self) -> None:
        self.act_as(self.faculty)
        student_id = self.student.student_profile.id
        self.assertEqual(self.client.get(f"/api/ml/prediction/{student_id}/").status_code, 200)

        other = self.enrol(self.classmate, self.django).student
        self.act_as(self.other_faculty)
        self.assertEqual(self.client.get(f"/api/ml/prediction/{student_id}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/ml/prediction/{other.id}/").status_code, 200)
        self.assertEqual(self.client.get("/api/ml/predictions/").json()["data"]["count"], 0)

    def test_prediction_list_filters(self) -> None:
        self.act_as(self.admin)
        rows = self.client.get("/api/ml/predictions/?indicator=GOOD&ordering=-predicted_final_score").json()["data"]["results"]
        self.assertEqual([row["student"]["full_name"] for row in rows], ["Rahul Sen"])
        self.assertEqual(self.client.get("/api/ml/predictions/?search=priya").json()["data"]["count"], 0)
        self.assertEqual(self.client.get("/api/ml/predictions/?indicator=BAD").status_code, 400)

    def test_student_cannot_use_staff_endpoints(self) -> None:
        self.act_as(self.student)
        self.assertEqual(self.client.get("/api/ml/predictions/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/ml/prediction/{self.student.student_profile.id}/").status_code, 403)
        self.act_as(self.faculty)
        self.assertEqual(self.client.get("/api/student/prediction/").status_code, 403)

    def test_deleting_a_student_removes_the_prediction(self) -> None:
        self.act_as(self.student)
        self.client.get("/api/student/prediction/")
        self.student.delete()
        self.assertFalse(Prediction.objects.exists())
        self.assertFalse(Performance.objects.filter(enrolment_id=self.rahul.id).exists())