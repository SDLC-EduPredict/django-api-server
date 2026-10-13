from django.contrib import admin
from courses.models import Course, CourseCategory


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "faculty", "level", "mode", "fee", "status", "start_date")
    list_filter = ("status", "level", "mode", "category")
    search_fields = ("title", "slug", "short_description", "faculty__first_name", "faculty__last_name")
    list_select_related = ("category", "faculty")
    autocomplete_fields = ("faculty",)
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")