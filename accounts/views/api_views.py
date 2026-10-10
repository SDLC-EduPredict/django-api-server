import logging

import jwt
from django.contrib.auth import authenticate
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination

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
from core.responses import error_response, success_response
from permissions.constants import EDIT_OWN_PROFILE, MANAGE_USERS, VIEW_OWN_PROFILE
from permissions.decorators import permission_required
from permissions.utils import get_permission_names

logger = logging.getLogger(__name__)


def user_with_permissions(user: User) -> dict:
    # The React panel / Flutter app uses "permissions" to decide which menus and buttons to show
    return {**UserSerializer(user).data, "permissions": get_permission_names(user.role)}


def otp_error(user, otp):
    return verify_otp(user, otp) if user else "Invalid OTP."


def issue_otp(user, channel):
    wait_seconds = seconds_to_wait(user)
    if wait_seconds:
        return error_response(f"Please wait {wait_seconds} seconds before requesting another OTP.", status_code=status.HTTP_429_TOO_MANY_REQUESTS)

    otp = create_otp(user, channel)

    try:
        send_otp(user, channel, otp)
    except Exception:
        logger.exception("Could not send the OTP to %s", user.email)
        OTP.objects.filter(user=user).delete()
        return error_response("OTP could not be sent. Please try again later.", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    logger.info("OTP sent by %s to %s", channel, user.email)
    return None


# ---------------------------------------------------------------- PUBLIC
@api_view(["POST"])
def register_view(request):
    form = RegisterForm(request.data)

    if not form.is_valid():
        return error_response("Registration failed.", form.errors)

    user = form.save()
    logger.info("New %s registered: %s", user.role, user.email)

    if user.role == User.Role.FACULTY:
        message = "Registration successful. Your faculty account will be activated after the administrator approves it."
    else:
        message = "Registration successful. Please login."
    return success_response(message, {"user": UserSerializer(user).data}, status.HTTP_201_CREATED)


@api_view(["POST"])
def login_view(request):
    form = LoginForm(request.data)

    if not form.is_valid():
        return error_response("Login failed.", form.errors)

    username = form.cleaned_data["username"]
    password = form.cleaned_data["password"]
    # authenticate() calls EmailOrPhoneBackend.authenticate() from backends.py since it's overwritten.
    user = authenticate(request, username=username, password=password)

    if user is None:
        inactive_user = User.objects.filter(Q(email__iexact=username) | Q(phone=username), is_active=False).first()
        if inactive_user and inactive_user.check_password(password):
            return error_response("Your account is not active. Please wait for the administrator to approve it.", status_code=status.HTTP_403_FORBIDDEN)

        logger.warning("Failed login attempt for '%s'", username)
        return error_response("Invalid Email/Phone or Password", status_code=status.HTTP_401_UNAUTHORIZED)

    logger.info("Login: %s (%s)", user.email, user.role)
    return success_response("Login successful.", {**build_token_response(user), "user": user_with_permissions(user)})


@api_view(["POST"])
def refresh_view(request):
    # Body: {"refresh_token": "..."}  ->  new access token + NEW refresh token (the old one is used up)
    token = request.data.get("refresh_token", "")

    try:
        payload = decode_token(token, REFRESH)
    except jwt.ExpiredSignatureError:
        return error_response("Refresh token expired. Please login again.", status_code=status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidTokenError:
        return error_response("Invalid refresh token.", status_code=status.HTTP_401_UNAUTHORIZED)

    record = RefreshToken.objects.select_related("user").filter(jti=payload["jti"]).first()

    if record is None or not record.is_usable or not record.user.is_active:
        # A refresh token that was already used / revoked is being replayed: treat it as suspicious
        logger.warning("Refresh rejected (revoked, used or unknown token) jti=%s", payload["jti"])
        return error_response("Refresh token is no longer valid. Please login again.", status_code=status.HTTP_401_UNAUTHORIZED)

    record.revoked = True
    record.save(update_fields=["revoked", "updated_at"])

    return success_response("Token refreshed.", build_token_response(record.user))


@api_view(["POST"])
def forgot_password_view(request):
    form = ForgotPasswordForm(request.data)

    if not form.is_valid():
        return error_response("Request failed.", form.errors)

    username = form.cleaned_data["username"]
    user = find_user(username)

    if user is None:
        logger.warning("Forgot password: no active account for '%s'", username)
    else:
        channel = OTP.Channel.EMAIL if "@" in username else OTP.Channel.SMS
        error = issue_otp(user, channel)
        if error:
            return error

    return success_response("If an account exists, an OTP has been sent.")


@api_view(["POST"])
def verify_phone_otp_view(request):
    form = VerifyPhoneOTPForm(request.data)

    if not form.is_valid():
        return error_response("Verification failed.", form.errors)

    error = otp_error(find_user(form.cleaned_data["phone"]), form.cleaned_data["otp"])
    if error:
        return error_response(error)
    return success_response("OTP verified successfully!")


@api_view(["POST"])
def verify_email_otp_view(request):
    form = VerifyEmailOTPForm(request.data)

    if not form.is_valid():
        return error_response("Verification failed.", form.errors)

    user = find_user(form.cleaned_data["email"])
    error = otp_error(user, form.cleaned_data["otp"])
    if error:
        return error_response(error)

    user.email_verified = True
    user.save(update_fields=["email_verified"])
    return success_response("OTP verified successfully! Your email is verified.")


@api_view(["POST"])
def reset_password_view(request):
    form = ResetPasswordForm(request.data)

    if not form.is_valid():
        return error_response("Password reset failed.", form.errors)

    user = find_user(form.cleaned_data["username"])
    error = otp_error(user, form.cleaned_data["otp"])
    if error:
        return error_response(error)

    user.set_password(form.cleaned_data["password"])
    user.save(update_fields=["password"])
    OTP.objects.filter(user=user).delete()
    revoke_all_refresh_tokens(user)
    return success_response("Password reset successful. Please login with your new password.")


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
        return error_response("A valid refresh_token is required to logout.")

    RefreshToken.objects.filter(jti=payload["jti"], user=request.user).update(revoked=True)
    logger.info("Logout: %s", request.user.email)
    return success_response("Logged out successfully.")


@api_view(["POST"])
@jwt_required
def send_email_verification_view(request):
    if request.user.email_verified:
        return success_response("Your email is already verified.")

    error = issue_otp(request.user, OTP.Channel.EMAIL)
    if error:
        return error
    return success_response("An OTP has been sent to your email. Send it to /api/auth/verify-email-otp/ to verify your email.")


@api_view(["GET"])
@jwt_required
@permission_required(VIEW_OWN_PROFILE)
def me_view(request):
    return success_response("Profile fetched successfully.", {"user": user_with_permissions(request.user)})


@api_view(["PATCH"])
@jwt_required
@permission_required(EDIT_OWN_PROFILE)
def profile_update_view(request):
    form = ProfileUpdateForm(with_current_values(request.user, ProfileUpdateForm, request.data), instance=request.user)

    if not form.is_valid():
        return error_response("Profile update failed.", form.errors)

    form.save()
    return success_response("Profile updated successfully!", {"user": user_with_permissions(request.user)})


@api_view(["POST"])
@jwt_required
def change_password_view(request):
    form = ChangePasswordForm(request.data, user=request.user)

    if not form.is_valid():
        return error_response("Password change failed.", form.errors)

    form.save()
    revoke_all_refresh_tokens(request.user)     # every device has to login again
    return success_response("Password changed. Please login again.")


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
        data = paginator.get_paginated_response(UserSerializer(page, many=True).data).data
        return success_response("Users fetched successfully.", data)

    form = AdminUserCreateForm(request.data)
    if not form.is_valid():
        return error_response("User creation failed.", form.errors)

    user = form.save()
    logger.info("User %s created by %s with role %s", user.email, request.user.email, user.role)
    return success_response("User created successfully!", {"user": UserSerializer(user).data}, status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@jwt_required
@role_required(User.Role.SUPER_ADMIN)
@permission_required(MANAGE_USERS)
def user_detail(request, user_id):
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return error_response("User not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return success_response("User fetched successfully.", {"user": user_with_permissions(user)})

    if user.pk == request.user.pk:
        return error_response("You cannot change or deactivate your own account here.")

    if request.method == "PATCH":
        form = AdminUserUpdateForm(with_current_values(user, AdminUserUpdateForm, request.data), instance=user)
        if not form.is_valid():
            return error_response("User update failed.", form.errors)

        user = form.save()
        if not user.is_active:
            revoke_all_refresh_tokens(user)
        logger.info("User %s updated by %s", user.email, request.user.email)
        return success_response("User updated successfully!", {"user": UserSerializer(user).data})

    # DELETE: we deactivate instead of deleting, because attendance, marks and predictions will point to this user
    user.is_active = False
    user.save(update_fields=["is_active"])
    revoke_all_refresh_tokens(user)
    logger.info("User %s deactivated by %s", user.email, request.user.email)
    return success_response("User deactivated successfully!")