from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from core.utils import module_context


def index(request: HttpRequest) -> HttpResponse:
    context: dict = module_context("enrolments")
    return render(request, "enrolments/index.html", context)