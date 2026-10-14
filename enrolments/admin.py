from django.contrib import admin
from enrolments.models import Enrolment


@admin.register(Enrolment)
class EnrolmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "status", "enrolled_on", "start_date", "end_date")
    list_filter = ("status", "course")
    search_fields = ("student__student_code", "student__user__email", "student__user__first_name", "course__title")
    list_select_related = ("student__user", "course")
    autocomplete_fields = ("student", "course")
    readonly_fields = ("created_at", "updated_at")