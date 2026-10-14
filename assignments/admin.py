from django.contrib import admin
from assignments.models import Assignment, AssignmentSubmission


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "due_date", "max_marks", "created_by")
    list_filter = ("course",)
    search_fields = ("title", "course__title")
    list_select_related = ("course", "created_by")
    readonly_fields = ("created_by", "created_at", "updated_at")


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "enrolment", "status", "submitted_at", "marks", "graded_by")
    list_filter = ("status", "assignment__course")
    search_fields = ("assignment__title", "enrolment__student__student_code", "enrolment__student__user__first_name")
    list_select_related = ("assignment", "enrolment__student__user", "graded_by")
    autocomplete_fields = ("enrolment",)
    readonly_fields = ("graded_by", "graded_at", "created_at", "updated_at")
