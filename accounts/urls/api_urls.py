from django.urls import path
from accounts.views import api_views

app_name = "accounts_api"



urlpatterns = [
    # Public
    path("auth/register/", api_views.register_view, name="register"),                                                       # POST
    path("auth/login/", api_views.login_view, name="login"),                                                                # POST
    path("auth/refresh/", api_views.refresh_view, name="refresh"),                                                          # POST
    path("auth/forgot-password/", api_views.forgot_password_view, name="forgot_password"),                                  # POST
    path("auth/verify-phone-otp/", api_views.verify_phone_otp_view, name="verify_phone_otp"),                               # POST
    path("auth/verify-email-otp/", api_views.verify_email_otp_view, name="verify_email_otp"),                               # POST
    path("auth/reset-password/", api_views.reset_password_view, name="reset_password"),                                     # POST

    # Needs an access token
    path("auth/logout/", api_views.logout_view, name="logout"),                                                             # POST
    path("auth/send-email-verification/", api_views.send_email_verification_view, name="send_email_verification"),          # POST
    path("auth/me/", api_views.me_view, name="me"),                                                                         # GET
    path("auth/profile/", api_views.profile_update_view, name="profile_update"),                                            # PATCH
    path("auth/change-password/", api_views.change_password_view, name="change_password"),                                  # POST
    path("faculty/profile/", api_views.faculty_profile_view, name="faculty_profile"),                                       # GET, PATCH

    # Super Admin (React admin panel)
    path("admin/users/", api_views.user_list_create, name="user_list_create"),                                              # SUPER ADMIN - GET, POST
    path("admin/users/<uuid:user_id>/", api_views.user_detail, name="user_detail"),                                         # SUPER ADMIN - GET, PATCH, DELETE
]