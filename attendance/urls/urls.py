from django.urls import path
from attendance.views import views

app_name = "attendance"


urlpatterns = [
    path("", views.index, name="index"),
]