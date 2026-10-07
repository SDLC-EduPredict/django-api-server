from django.contrib import admin
from permissions.models import Permission, RolePermission


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission")
    list_filter = ("role",)
    search_fields = ("permission__name",)