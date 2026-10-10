import logging
from functools import wraps
import jwt
from rest_framework import status
from accounts.models import User
from accounts.tokens import ACCESS, decode_token
from core.responses import error_response

logger = logging.getLogger(__name__)


# Replaces @login_required of the session based project. Reads "Authorization: Bearer <access_token>", checks it and sets request.user
def jwt_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")

        if scheme.lower() != "bearer" or not token:
            return error_response("Authentication required. Send the header: Authorization: Bearer <access_token>", status_code=status.HTTP_401_UNAUTHORIZED)

        try:
            payload = decode_token(token, ACCESS)
        except jwt.ExpiredSignatureError:
            return error_response("Access token expired. Use the refresh token to get a new one.", status_code=status.HTTP_401_UNAUTHORIZED)
        except jwt.InvalidTokenError as error:
            logger.warning("Invalid access token: %s", error)
            return error_response("Invalid access token.", status_code=status.HTTP_401_UNAUTHORIZED)

        user = User.objects.filter(pk=payload["user_id"], is_active=True).first()
        if user is None:
            return error_response("User not found or inactive.", status_code=status.HTTP_401_UNAUTHORIZED)

        request.user = user
        return view_func(request, *args, **kwargs)

    return wrapper


# Must be placed BELOW @jwt_required, because it needs request.user
def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                logger.warning("Role denied: user=%s role=%s allowed=%s path=%s", request.user.email, request.user.role, ", ".join(allowed_roles), request.path)
                return error_response("You do not have permission to access this resource.", status_code=status.HTTP_403_FORBIDDEN)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator