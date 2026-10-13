from django.urls import path
from assessments.views import api_views

app_name = "assessments_api"


urlpatterns = [
    path("student/results/", api_views.student_results, name="student_results"),

    path("assessments/", api_views.assessment_list_create, name="assessment_list_create"),
    path("assessments/<int:assessment_id>/", api_views.assessment_detail, name="assessment_detail"),
    path("assessments/<int:assessment_id>/results/", api_views.assessment_results, name="assessment_results"),
    path("assessments/results/<int:result_id>/", api_views.result_delete, name="result_delete"),
]
