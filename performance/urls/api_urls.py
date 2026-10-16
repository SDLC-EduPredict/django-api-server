from django.urls import path
from performance.views import api_views

app_name = "performance_api"


urlpatterns = [
    path("student/performance/", api_views.student_performance, name="student_performance"),                                # STUDENT - GET

    path("performance/", api_views.performance_list, name="performance_list"),                                              # STAFF - GET
    path("performance/summary/", api_views.course_performance_summary, name="course_performance_summary"),                  # STAFF - GET
    path("performance/dataset/", api_views.ml_dataset, name="ml_dataset"),                                                  # STAFF - GET
    path("performance/<int:performance_id>/", api_views.performance_detail, name="performance_detail"),                     # STAFF - GET, PATCH
]