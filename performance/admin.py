from django.contrib import admin
from performance.models import Performance
from performance.utils import calculate_performance


@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "attendance_percentage", "assignment_average", "mock_test_average", "modules_completed_percentage", "overall_score", "indicator")
    list_filter = ("indicator", "participation", "enrolment__status", "enrolment__course")
    search_fields = ("enrolment__student__student_code", "enrolment__student__user__first_name", "enrolment__student__user__last_name", "enrolment__course__title")
    list_select_related = ("enrolment__student__user", "enrolment__course")
    fields = ("enrolment", "practice_hours", "previous_score", "modules_completed", "participation") + tuple(Performance.CALCULATED_FIELDS) + ("updated_by", "created_at", "updated_at")
    readonly_fields = ("enrolment", "updated_by", "created_at", "updated_at") + tuple(Performance.CALCULATED_FIELDS)

    def has_add_permission(self, request) -> bool:
        return False

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        calculate_performance(obj)
        super().save_model(request, obj, form, change)