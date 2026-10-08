from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.decorators import jwt_required, role_required
from accounts.models import User
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
    return Response({
        "message": "All permissions and the permissions of every role",
        "permissions": all_permissions,
        "roles": roles_with_permissions(),
    }, status=status.HTTP_200_OK)


@api_view(["GET", "PUT"])
@jwt_required
@role_required(User.Role.SUPER_ADMIN)
@permission_required(MANAGE_PERMISSIONS)
def role_permissions(request, role):
    if role not in User.Role.values:
        return Response({"message": f"Unknown role '{role}'."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response({"role": role, "permissions": get_permission_names(role)}, status=status.HTTP_200_OK)

    # PUT: replace the permissions of the role with the list that was sent
    if role == User.Role.SUPER_ADMIN:
        return Response({
            "message": "The Super Admin always has every permission and cannot be edited."
        }, status=status.HTTP_400_BAD_REQUEST)

    form = RolePermissionsForm(request.data, role=role)
    if not form.is_valid():
        return Response({
            "message": "Update failed.", 
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    saved = form.save()
    return Response({
        "message": "Role permissions updated successfully!",
        "role": role,
        "permissions": saved
    })