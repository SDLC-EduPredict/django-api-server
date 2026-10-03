from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

def create_user(request: HttpRequest) -> HttpResponse:
    context: dict = {}
    return render(request, 'accounts/create_user.html', context)