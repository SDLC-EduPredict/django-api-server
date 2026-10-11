from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.forms import UserAdminChangeForm, UserAdminCreationForm
from accounts.models import OTP, FacultyProfile, RefreshToken, User
from students.models import StudentProfile


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    extra = 0
    max_num = 1
    can_delete = False


class FacultyProfileInline(admin.StackedInline):
    model = FacultyProfile
    extra = 0
    max_num = 1
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff", "email_verified")
    search_fields = ("email", "first_name", "last_name", "phone")
    readonly_fields = ("id", "last_login", "date_joined")

    fieldsets: tuple = (
        (None, {"fields": ("id", "email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone")}),
        ("Role", {"fields": ("role", "email_verified")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),)

    add_fieldsets = [
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "phone", "role", "password1", "password2"),
        }),
    ]

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        inline_by_role = {
            User.Role.STUDENT: StudentProfileInline,
            User.Role.FACULTY: FacultyProfileInline,
        }
        inline_class = inline_by_role.get(obj.role)
        return [inline_class(self.model, self.admin_site)] if inline_class else []


@admin.register(FacultyProfile)
class FacultyProfileAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "user", "designation", "expertise")
    search_fields = ("employee_code", "user__email", "user__first_name", "user__last_name", "expertise")
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "jti", "expires_at", "revoked", "created_at")
    list_filter = ("revoked",)
    search_fields = ("user__email", "jti")
    list_select_related = ("user",)
    readonly_fields = ("jti", "user", "expires_at", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ("user", "channel", "attempts", "expires_at", "created_at")
    list_filter = ("channel",)
    search_fields = ("user__email",)
    list_select_related = ("user",)
    readonly_fields = ("user", "channel", "otp_hash", "expires_at", "attempts", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        return False