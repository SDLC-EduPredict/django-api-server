import logging
from django.db import DatabaseError, connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from core.utils import project_counts


logger = logging.getLogger("django")


def home(request: HttpRequest) -> HttpResponse:
    context: dict = {"entities": project_counts()}
    return render(request, "core/home.html", context)


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logger.exception("Health check failed")
        return JsonResponse({"status": "error", "database": "down"}, status=503)
    return JsonResponse({"status": "ok", "database": "up", "engine": connection.vendor})