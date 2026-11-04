from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Templates
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls.urls")),
    path("students/", include("students.urls.urls")),
    path("courses/", include("courses.urls.urls")),
    path("enrolments/", include("enrolments.urls.urls")),
    path("attendance/", include("attendance.urls.urls")),
    path("assignments/", include("assignments.urls.urls")),
    path("assessments/", include("assessments.urls.urls")),
    path("performance/", include("performance.urls.urls")),
    path("predictions/", include("ml_prediction.urls.urls")),
    path("notifications/", include("notifications.urls.urls")),
    path("analytics/", include("analytics.urls.urls")),


    # APIs
    path("api/", include("accounts.urls.api_urls")),            # Login, Register, Refresh, Logout, Me, Admin Users
    path("api/", include("permissions.urls")),                  # Roles and Permissions (Super Admin)
    path("api/", include("courses.urls.api_urls")),             # Courses
    path("api/", include("students.urls.api_urls")),            # Students
    path("api/", include("enrolments.urls.api_urls")),          # Enrolments
    path("api/", include("attendance.urls.api_urls")),          # Attendance
    path("api/", include("assignments.urls.api_urls")),         # Assignments
    path("api/", include("assessments.urls.api_urls")),         # Assessments
    path("api/", include("performance.urls.api_urls")),         # Performance
    path("api/", include("ml_prediction.urls.api_urls")),       # ML Prediction
    path("api/", include("notifications.urls.api_urls")),       # Notifications
    path("api/", include("analytics.urls.api_urls")),           # Analytics
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)