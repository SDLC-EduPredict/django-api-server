from django.urls import path
from assignments.views import api_views

app_name = "assignments_api"


urlpatterns = [
    path("student/assignments/", api_views.student_assignments, name="student_assignments"),
    path("student/assignments/<int:assignment_id>/submit/", api_views.submit_assignment, name="submit_assignment"),

    path("assignments/", api_views.assignment_list_create, name="assignment_list_create"),
    path("assignments/<int:assignment_id>/", api_views.assignment_detail, name="assignment_detail"),
    path("assignments/<int:assignment_id>/submissions/", api_views.assignment_submissions, name="assignment_submissions"),
]
