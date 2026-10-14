from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from core.utils import module_context


def index(request: HttpRequest) -> HttpResponse:
    context: dict = module_context("attendance")
    return render(request, "attendance/index.html", context)
