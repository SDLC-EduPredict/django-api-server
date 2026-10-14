from django.contrib import admin
from attendance.models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "date", "status", "marked_by")
    list_filter = ("status", "date", "enrolment__course")
    search_fields = ("enrolment__student__student_code", "enrolment__student__user__first_name", "enrolment__course__title")
    list_select_related = ("enrolment__student__user", "enrolment__course", "marked_by")
    autocomplete_fields = ("enrolment",)
    readonly_fields = ("marked_by", "created_at", "updated_at")
    date_hierarchy = "date"