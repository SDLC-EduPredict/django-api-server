from django.contrib import admin
from students.models import StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("student_code", "user", "gender", "city", "created_at")
    list_filter = ("gender", "city")
    search_fields = ("student_code", "user__email", "user__first_name", "user__last_name", "user__phone")
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    readonly_fields = ("student_code", "created_at", "updated_at")