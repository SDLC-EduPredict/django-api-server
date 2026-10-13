from django.urls import path
from students.views import api_views

app_name = "students_api"


urlpatterns = [
    path("student/profile/", api_views.student_profile_view, name="student_profile"),                               # GET, PATCH
    path("student/dashboard/", api_views.student_dashboard_view, name="student_dashboard"),                         # GET

    # ADMIN
    path("admin/students/", api_views.admin_student_list, name="admin_student_list"),                               # ADMIN - GET
    path("admin/students/<int:student_id>/", api_views.admin_student_detail, name="admin_student_detail"),          # ADMIN - GET, PATCH
]