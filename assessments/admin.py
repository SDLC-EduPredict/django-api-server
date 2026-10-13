from django.contrib import admin
from assessments.models import Assessment, AssessmentResult


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "assessment_type", "assessment_date", "max_marks", "pass_marks")
    list_filter = ("assessment_type", "course")
    search_fields = ("title", "course__title")
    list_select_related = ("course",)
    readonly_fields = ("created_by", "created_at", "updated_at")


@admin.register(AssessmentResult)
class AssessmentResultAdmin(admin.ModelAdmin):
    list_display = ("assessment", "enrolment", "marks_obtained", "entered_by", "updated_at")
    list_filter = ("assessment__assessment_type", "assessment__course")
    search_fields = ("assessment__title", "enrolment__student__student_code", "enrolment__student__user__first_name")
    list_select_related = ("assessment", "enrolment__student__user", "entered_by")
    autocomplete_fields = ("enrolment",)
    readonly_fields = ("entered_by", "created_at", "updated_at")
