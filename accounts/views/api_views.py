import logging

import jwt
from django.contrib.auth import authenticate
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from accounts.decorators import jwt_required, role_required
from accounts.forms import (
    AdminUserCreateForm,
    AdminUserUpdateForm,
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    ProfileUpdateForm,
    RegisterForm,
    ResetPasswordForm,
    VerifyEmailOTPForm,
    VerifyPhoneOTPForm,
    with_current_values)
from accounts.models import OTP, RefreshToken, User
from accounts.otp import create_otp, find_user, seconds_to_wait, send_otp, verify_otp
from accounts.serializers import UserSerializer
from accounts.tokens import REFRESH, build_token_response, decode_token, revoke_all_refresh_tokens
from permissions.constants import EDIT_OWN_PROFILE, MANAGE_USERS, VIEW_OWN_PROFILE
from permissions.decorators import permission_required
from permissions.utils import get_permission_names

logger = logging.getLogger(__name__)


def user_with_permissions(user: User) -> dict:
    # The React panel / Flutter app uses "permissions" to decide which menus and buttons to show
    return {**UserSerializer(user).data, "permissions": get_permission_names(user.role)}


# ---------------------------------------------------------------- PUBLIC
@api_view(["POST"])
def register_view(request):
    form = RegisterForm(request.data)

    if not form.is_valid():
        return Response({
            "message": "Registration failed.",
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    user = form.save()
    logger.info("New student registered: %s", user.email)
    return Response({
        "message": "Registration successful. Please login.",
        "user": UserSerializer(user).data
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def login_view(request):
    form = LoginForm(request.data)

    if not form.is_valid():
        return Response({
            "message": "Login failed.",
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    username = form.cleaned_data["username"]
    # authenticate() calls EmailOrPhoneBackend.authenticate() from backends.py since it's overwritten.
    user = authenticate(request, username=username, password=form.cleaned_data["password"])

    if user is None:
        logger.warning("Failed login attempt for '%s'", username)
        return Response({
            "message": "Invalid Email/Phone or Password"
        }, status=status.HTTP_401_UNAUTHORIZED)

    logger.info("Login: %s (%s)", user.email, user.role)
    return Response({
        "message": "Login successful.", **build_token_response(user),
        "user": user_with_permissions(user)
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
def refresh_view(request) -> Response:
    # Body: {"refresh_token": "..."}  ->  new access token + NEW refresh token (the old one is used up)
    token = request.data.get("refresh_token", "")

    try:
        payload = decode_token(token, REFRESH)
    except jwt.ExpiredSignatureError:
        return Response({
            "message": "Refresh token expired. Please login again."
        }, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidTokenError:
        return Response({
            "message": "Invalid refresh token."
        }, status=status.HTTP_401_UNAUTHORIZED)

    record = RefreshToken.objects.select_related("user").filter(jti=payload["jti"]).first()

    if record is None or not record.is_usable or not record.user.is_active:
        # A refresh token that was already used / revoked is being replayed: treat it as suspicious
        logger.warning("Refresh rejected (revoked, used or unknown token) jti=%s", payload["jti"])
        return Response({
            "message": "Refresh token is no longer valid. Please login again."
        }, status=status.HTTP_401_UNAUTHORIZED)

    record.revoked = True
    record.save(update_fields=["revoked", "updated_at"])

    return Response({
        "message": "Token refreshed.", **build_token_response(record.user)
    }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------- LOGGED IN USER
@api_view(["POST"])
@jwt_required
def logout_view(request):
    # Body: {"refresh_token": "..."}  ->  that refresh token can never be used again.
    # The access token stays valid until it expires, usually 15 minutes. The client must delete it.
    token = request.data.get("refresh_token", "")

    try:
        payload = decode_token(token, REFRESH)
    except jwt.InvalidTokenError:
        return Response({
            "message": "A valid refresh_token is required to logout."
        }, status=status.HTTP_400_BAD_REQUEST)

    RefreshToken.objects.filter(jti=payload["jti"], user=request.user).update(revoked=True)
    logger.info("Logout: %s", request.user.email)
    return Response({
        "message": "Logged out successfully."
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@jwt_required
@permission_required(VIEW_OWN_PROFILE)
def me_view(request):
    return Response({
        "user": user_with_permissions(request.user)
    }, status=status.HTTP_200_OK)


@api_view(["PATCH"])
@jwt_required
@permission_required(EDIT_OWN_PROFILE)
def profile_update_view(request):
    form = ProfileUpdateForm(with_current_values(request.user, ProfileUpdateForm, request.data), instance=request.user)

    if not form.is_valid():
        return Response({
            "message": "Profile update failed.",
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    form.save()
    return Response({
        "message": "Profile updated successfully!",
        "user": user_with_permissions(request.user)
    })


@api_view(["POST"])
@jwt_required
def change_password_view(request):
    form = ChangePasswordForm(request.data, user=request.user)

    if not form.is_valid():
        return Response({
            "message": "Password change failed.",
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    form.save()
    revoke_all_refresh_tokens(request.user)     # every device has to login again
    return Response({
        "message": "Password changed. Please login again."
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
def forgot_password_view(request):
    form = ForgotPasswordForm(request.data)

    if not form.is_valid():
        return Response({
            "message": "Request failed.",
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    username = form.cleaned_data["username"]
    user = find_user(username)
    same_answer = Response({
        "message": "If an account exists, an OTP has been sent."
    }, status=status.HTTP_200_OK)

    if user is None:
        return same_answer

    wait_seconds = seconds_to_wait(user)
    if wait_seconds:
        return Response({
            "message": f"Please wait {wait_seconds} seconds before requesting another OTP."
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    channel = OTP.Channel.EMAIL if "@" in username else OTP.Channel.SMS
    otp = create_otp(user, channel)

    try:
        send_otp(user, channel, otp)
    except Exception:
        logger.exception("Could not send the OTP to %s", user.email)
        OTP.objects.filter(user=user).delete()
        return Response({
            "message": "OTP could not be sent. Please try again later."
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return same_answer


def otp_response(user, otp):
    error = verify_otp(user, otp) if user else "Invalid OTP."

    if error:
        return Response({"message": error}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"message": "OTP verified successfully!"}, status=status.HTTP_200_OK)


@api_view(["POST"])
def verify_phone_otp_view(request):
    form = VerifyPhoneOTPForm(request.data)

    if not form.is_valid():
        return Response({
            "message": "Verification failed.",
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    user = find_user(form.cleaned_data["phone"])
    return otp_response(user, form.cleaned_data["otp"])


@api_view(["POST"])
def verify_email_otp_view(request):
    form = VerifyEmailOTPForm(request.data)

    if not form.is_valid():
        return Response({
            "message": "Verification failed.",
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    user = find_user(form.cleaned_data["email"])
    return otp_response(user, form.cleaned_data["otp"])


@api_view(["POST"])
def reset_password_view(request):
    form = ResetPasswordForm(request.data)

    if not form.is_valid():
        return Response({
            "message": "Password reset failed.",
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    user = find_user(form.cleaned_data["username"])
    error = verify_otp(user, form.cleaned_data["otp"]) if user else "Invalid OTP."

    if error:
        return Response({"message": error}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(form.cleaned_data["password"])
    user.save(update_fields=["password"])
    OTP.objects.filter(user=user).delete()
    revoke_all_refresh_tokens(user)
    return Response({
        "message": "Password reset successful. Please login with your new password."
    }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------- ADMIN PANEL (React)
@api_view(["GET", "POST"])
@jwt_required
@role_required(User.Role.SUPER_ADMIN)
@permission_required(MANAGE_USERS)
def user_list_create(request):
    if request.method == "GET":
        users = User.objects.all()

        role = request.query_params.get("role")
        search = request.query_params.get("search")
        is_active = request.query_params.get("is_active")

        if role:
            users = users.filter(role=role)
        if search:
            users = users.filter(
                Q(email__icontains=search) | Q(first_name__icontains=search)
                | Q(last_name__icontains=search) | Q(phone__icontains=search))
        if is_active in ("true", "false"):
            users = users.filter(is_active=(is_active == "true"))

        paginator = PageNumberPagination()      # ?page=2&page_size=10 (PAGE_SIZE is set in settings.py)
        paginator.page_size_query_param = "page_size"
        page = paginator.paginate_queryset(users, request)
        return paginator.get_paginated_response(UserSerializer(page, many=True).data)

    form = AdminUserCreateForm(request.data)
    if not form.is_valid():
        return Response({
            "message": "User creation failed.", 
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    user = form.save()
    logger.info("User %s created by %s with role %s", user.email, request.user.email, user.role)
    return Response({
        "message": "User created successfully!",
        "user": UserSerializer(user).data
    }, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@jwt_required
@role_required(User.Role.SUPER_ADMIN)
@permission_required(MANAGE_USERS)
def user_detail(request, user_id):
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return Response({
            "message": "User not found."
        }, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response({
            "user": user_with_permissions(user)
        }, status=status.HTTP_200_OK)

    if user.pk == request.user.pk:
        return Response({
            "message": "You cannot change or deactivate your own account here."
        }, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "PATCH":
        form = AdminUserUpdateForm(with_current_values(user, AdminUserUpdateForm, request.data), instance=user)
        if not form.is_valid():
            return Response({
                "message": "User update failed.",
                "errors": form.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        user = form.save()
        if not user.is_active:
            revoke_all_refresh_tokens(user)
        logger.info("User %s updated by %s", user.email, request.user.email)
        return Response({
            "message": "User updated successfully!",
            "user": UserSerializer(user).data
        })

    # DELETE: we deactivate instead of deleting, because attendance, marks and predictions will point to this user
    user.is_active = False
    user.save(update_fields=["is_active"])
    revoke_all_refresh_tokens(user)
    logger.info("User %s deactivated by %s", user.email, request.user.email)
    return Response({
        "message": "User deactivated successfully!"
    }, status=status.HTTP_200_OK)