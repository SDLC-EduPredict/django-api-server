from django.urls import path
from performance.views import views

app_name = "performance"


urlpatterns = [
    path("", views.index, name="index"),
]