from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required, role_required
from accounts.models import User
from core.responses import error_response, success_response
from permissions.constants import MANAGE_PERMISSIONS
from permissions.decorators import permission_required
from permissions.forms import RolePermissionsForm
from permissions.models import Permission
from permissions.serializers import PermissionSerializer
from permissions.utils import get_permission_names


def roles_with_permissions() -> dict[str, list[str]]:
    result = {}
    for role, _ in User.Role.choices:
        result[role] = get_permission_names(role)
    return result


@api_view(["GET"])
@jwt_required
@role_required(User.Role.SUPER_ADMIN)
@permission_required(MANAGE_PERMISSIONS)
def permission_list(request):
    all_permissions = PermissionSerializer(Permission.objects.all(), many=True).data
    return success_response("All permissions and the permissions of every role.", {
        "permissions": all_permissions,
        "roles": roles_with_permissions(),
    })


@api_view(["GET", "PUT"])
@jwt_required
@role_required(User.Role.SUPER_ADMIN)
@permission_required(MANAGE_PERMISSIONS)
def role_permissions(request, role):
    if role not in User.Role.values:
        return error_response(f"Unknown role '{role}'.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return success_response("Role permissions fetched successfully.", {
            "role": role,
            "permissions": get_permission_names(role),
        })

    # PUT: replace the permissions of the role with the list that was sent
    if role == User.Role.SUPER_ADMIN:
        return error_response("The Super Admin always has every permission and cannot be edited.")

    form = RolePermissionsForm(request.data, role=role)
    if not form.is_valid():
        return error_response("Update failed.", form.errors)

    saved = form.save()
    return success_response("Role permissions updated successfully!", {
        "role": role,
        "permissions": saved,
    })