from django.urls import path
from attendance.views import api_views

app_name = "attendance_api"


urlpatterns = [
    path("student/attendance/", api_views.student_attendance, name="student_attendance"),

    path("attendance/", api_views.attendance_list_create, name="attendance_list_create"),
    path("attendance/summary/", api_views.attendance_summary_view, name="attendance_summary"),
    path("attendance/<int:attendance_id>/", api_views.attendance_detail, name="attendance_detail"),
]
