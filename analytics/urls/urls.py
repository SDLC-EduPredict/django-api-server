from django.urls import path
from analytics.views import views

app_name = "analytics"


urlpatterns = [
    path("", views.index, name="index"),
]