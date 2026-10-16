from django.urls import path
from ml_prediction.views import api_views

app_name = "ml_prediction_api"


urlpatterns = [
    path("student/prediction/", api_views.student_prediction, name="student_prediction"),                                                   # STUDENT - GET

    path("ml/predict/", api_views.predict, name="predict"),                                                                                 # ADMIN - POST
    path("ml/predictions/", api_views.prediction_list, name="prediction_list"),                                                             # STAFF - GET
    path("ml/prediction/<int:student_id>/", api_views.student_prediction_detail, name="student_prediction_detail"),                         # STAFF - GET

    path("ml/train/", api_views.train_model, name="train_model"),                                                                           # ADMIN - POST
    path("ml/models/", api_views.model_list, name="model_list"),                                                                            # ADMIN - GET
    path("ml/models/<int:model_id>/activate/", api_views.activate_model_version, name="activate_model"),                                    # ADMIN - POST 
]