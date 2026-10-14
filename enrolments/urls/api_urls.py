from django.urls import path
from enrolments.views import api_views

app_name = "enrolments_api"


urlpatterns = [
    path("student/courses/", api_views.student_courses, name="student_courses"),                                        # STUDENT - GET, POST
    path("student/courses/<int:enrolment_id>/", api_views.student_course_detail, name="student_course_detail"),         # STUDENT - GET

    path("enrolments/", api_views.enrolment_list_create, name="enrolment_list_create"),                                 # STAFF - GET, POST
    path("enrolments/<int:enrolment_id>/", api_views.enrolment_detail, name="enrolment_detail"),                        # STAFF - GET, PATCH, DELETE
]