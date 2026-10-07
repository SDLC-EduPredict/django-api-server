from django.db import models
from accounts.models import User


class Permission(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class RolePermission(models.Model):
    role = models.CharField(max_length=20, choices=User.Role.choices)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="role_permissions")

    class Meta:
        unique_together = ("role", "permission")
        ordering = ["role", "permission__name"]

    def __str__(self) -> str:
        return f"{self.role} -> {self.permission.name}"