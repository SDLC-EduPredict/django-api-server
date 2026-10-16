from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from core.utils import module_context


def index(request: HttpRequest) -> HttpResponse:
    context: dict = module_context("ml_prediction")
    return render(request, "ml_prediction/index.html", context)