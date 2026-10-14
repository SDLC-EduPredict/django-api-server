from django.urls import path
from assignments.views import views

app_name = "assignments"


urlpatterns = [
    path("", views.index, name="index"),
]
