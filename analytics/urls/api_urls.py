from django.urls import path
from analytics.views import api_views

app_name = "analytics_api"


urlpatterns = [
    path("admin/dashboard/", api_views.admin_dashboard, name="admin_dashboard"),                                                            # ADMIN - GET
    path("faculty/dashboard/", api_views.faculty_dashboard, name="faculty_dashboard"),                                                      # FACULTY - GET
    path("faculty/students/", api_views.my_students, name="my_students"),                                                                   # STAFF - GET
    path("faculty/students/<int:student_id>/", api_views.student_report, name="student_report"),                                            # STAFF - GET

    path("reports/overview/", api_views.report_overview, name="report_overview"),                                                           # STAFF - GET
    path("reports/course-performance/", api_views.course_performance_report, name="course_performance_report"),                             # STAFF - GET
    path("reports/students-needing-attention/", api_views.attention_report, name="attention_report"),                                       # STAFF - GET
    path("reports/prediction-distribution/", api_views.prediction_distribution_report, name="prediction_distribution_report"),              # STAFF - GET
]