from django.urls import path
from assessments.views import api_views

app_name = "assessments_api"


urlpatterns = [
    path("student/results/", api_views.student_results, name="student_results"),                                                # STUDENT - GET

    path("assessments/", api_views.assessment_list_create, name="assessment_list_create"),                                      # STAFF - GET, POST
    path("assessments/<int:assessment_id>/", api_views.assessment_detail, name="assessment_detail"),                            # STAFF - GET, PATCH, DELETE
    path("assessments/<int:assessment_id>/results/", api_views.assessment_results, name="assessment_results"),                  # STAFF - GET, POST
    path("assessments/results/<int:result_id>/", api_views.result_delete, name="result_delete"),                                # STAFF - DELETE
]