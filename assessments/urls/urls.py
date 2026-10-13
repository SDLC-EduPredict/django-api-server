from django.urls import path
from assessments.views import views

app_name = "assessments"


urlpatterns = [
    path("", views.index, name="index"),
]
