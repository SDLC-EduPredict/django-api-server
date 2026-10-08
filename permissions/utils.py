from accounts.models import User
from permissions.models import Permission, RolePermission


# The Super Admin always has every permission (so he can never lock himself out)
def get_permission_names(role: str) -> list[str]:
    if role == User.Role.SUPER_ADMIN:
        return list(Permission.objects.values_list("name", flat=True))
    return list(RolePermission.objects
            .filter(role=role)
            .values_list("permission__name", flat=True)
            .order_by("permission__name"))