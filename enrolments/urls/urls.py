from django.urls import path
from enrolments.views import views

app_name = "enrolments"


urlpatterns = [
    path("", views.index, name="index"),
]
