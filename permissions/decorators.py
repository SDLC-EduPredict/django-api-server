import logging
from functools import wraps
from rest_framework import status
from rest_framework.response import Response

from accounts.models import User
from permissions.models import RolePermission

logger = logging.getLogger(__name__)


def permission_required(permission_name):
    # While consuming, this must be placed BELOW @jwt_required, because it needs request.user
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user_role = request.user.role

            is_super_admin = user_role == User.Role.SUPER_ADMIN
            permission_exists = RolePermission.objects.filter(role=user_role, permission__name=permission_name).exists()

            if not (is_super_admin or permission_exists):
                logger.warning(
                    "Permission denied: user=%s role=%s needs=%s path=%s",
                    request.user.email,
                    user_role,
                    permission_name,
                    request.path)
                return Response({
                    "message": "You do not have permission to perform this action.",
                    "required_permission": permission_name
                }, status=status.HTTP_403_FORBIDDEN)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator