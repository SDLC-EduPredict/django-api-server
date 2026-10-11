from django.urls import path
from courses.views import views

app_name = "courses"


urlpatterns = [
    path("", views.index, name="index"),
]
