from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls.urls")),
    path("students/", include("students.urls.urls")),
    path("courses/", include("courses.urls.urls")),
    path("enrolments/", include("enrolments.urls.urls")),
    path("attendance/", include("attendance.urls.urls")),
    path("assignments/", include("assignments.urls.urls")),
    path("assessments/", include("assessments.urls.urls")),
    # path("performance/", include("performance.urls.urls")),
    # path("predictions/", include("ml_prediction.urls.urls")),
    # path("notifications/", include("notifications.urls.urls")),


    # APIs
    path("api/", include("accounts.urls.api_urls")),            # login, register, refresh, logout, me, admin users
    path("api/", include("permissions.urls")),                  # roles and permissions (Super Admin)
    path("api/", include("courses.urls.api_urls")),
    path("api/", include("students.urls.api_urls")),
    path("api/", include("enrolments.urls.api_urls")),
    path("api/", include("attendance.urls.api_urls")),
    path("api/", include("assignments.urls.api_urls")),
    path("api/", include("assessments.urls.api_urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)