from django.urls import path
from accounts.views import api_views

app_name = "accounts_api"



urlpatterns = [
    # Public
    path("auth/register/", api_views.register_view, name="register"),
    path("auth/login/", api_views.login_view, name="login"),
    path("auth/refresh/", api_views.refresh_view, name="refresh"),

    # Needs an access token
    path("auth/logout/", api_views.logout_view, name="logout"),
    path("auth/me/", api_views.me_view, name="me"),
    path("auth/profile/", api_views.profile_update_view, name="profile_update"),
    path("auth/change-password/", api_views.change_password_view, name="change_password"),
    path("auth/forgot-password/", api_views.forgot_password_view, name="forgot_password"),

    # Super Admin (React admin panel)
    path("admin/users/", api_views.user_list_create, name="user_list_create"),
    path("admin/users/<uuid:user_id>/", api_views.user_detail, name="user_detail"),
]