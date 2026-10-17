from django.urls import path
from notifications.views import views

app_name = "notifications"


urlpatterns = [
    path("", views.index, name="index"),
]