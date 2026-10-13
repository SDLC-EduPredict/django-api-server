from django.urls import path
from enrolments.views import api_views

app_name = "enrolments_api"


urlpatterns = [
    path("student/courses/", api_views.student_courses, name="student_courses"),
    path("student/courses/<int:enrolment_id>/", api_views.student_course_detail, name="student_course_detail"),

    path("enrolments/", api_views.enrolment_list_create, name="enrolment_list_create"),
    path("enrolments/<int:enrolment_id>/", api_views.enrolment_detail, name="enrolment_detail"),
]
