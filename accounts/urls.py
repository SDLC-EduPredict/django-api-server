from django.contrib import admin
from django.urls import path
from accounts import views

urlpatterns = [
    path('/create-user', views.create_user, name='create_user'),
]
