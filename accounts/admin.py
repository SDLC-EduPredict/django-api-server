from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.forms import UserAdminChangeForm, UserAdminCreationForm
from accounts.models import FacultyProfile, User


class StudentProfileInline(admin.StackedInline):
    extra = 1
    max_num = 1
    can_delete = False


class FacultyProfileInline(admin.StackedInline):
    model = FacultyProfile
    extra = 1
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

    add_fieldsets = ((None, {
        "classes": ("wide",),
        "fields": ("email", "first_name", "last_name", "phone", "role", "password1", "password2"),
    }))

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