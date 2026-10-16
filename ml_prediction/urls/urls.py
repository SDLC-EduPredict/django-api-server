from django.urls import path
from ml_prediction.views import views

app_name = "ml_prediction"


urlpatterns = [
    path("", views.index, name="index"),
]