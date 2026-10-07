from django.urls import path
from permissions import views

app_name = "permissions"

urlpatterns = [
    path("admin/permissions/", views.permission_list, name="permission_list"),
    path("admin/roles/<str:role>/permissions/", views.role_permissions, name="role_permissions"),
]