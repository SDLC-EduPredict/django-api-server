from django.urls import path
from students.views import views

app_name = "students"


urlpatterns = [
    path("", views.index, name="index"),
]