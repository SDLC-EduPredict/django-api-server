from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    # path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    # path("students/", include("students.urls")),
    # path("courses/", include("courses.urls")),
    # path("enrolments/", include("enrolments.urls")),
    # path("attendance/", include("attendance.urls")),
    # path("assignments/", include("assignments.urls")),
    # path("assessments/", include("assessments.urls")),
    # path("performance/", include("performance.urls")),
    # path("predictions/", include("ml_prediction.urls")),
    # path("notifications/", include("notifications.urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)