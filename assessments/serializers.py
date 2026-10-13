from rest_framework import serializers
from assessments.models import Assessment, AssessmentResult
from enrolments.serializers import CourseShortSerializer, StudentShortSerializer


class AssessmentSerializer(serializers.ModelSerializer):
    course = CourseShortSerializer(read_only=True)
    assessment_type_display = serializers.CharField(source="get_assessment_type_display", read_only=True)
    created_by = serializers.CharField(source="created_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = Assessment
        fields = (
            "id", "course", "title", "assessment_type", "assessment_type_display", "description", "assessment_date",
            "max_marks", "pass_marks", "created_by", "created_at", "updated_at")
        read_only_fields = fields


class ResultSerializer(serializers.ModelSerializer):
    student = StudentShortSerializer(source="enrolment.student", read_only=True)
    marks_obtained = serializers.DecimalField(max_digits=5, decimal_places=2, coerce_to_string=False, read_only=True)
    percentage = serializers.FloatField(read_only=True)
    result = serializers.CharField(read_only=True)
    entered_by = serializers.CharField(source="entered_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = AssessmentResult
        fields = ("id", "assessment", "enrolment", "student", "marks_obtained", "percentage", "result", "remarks", "entered_by", "updated_at")
        read_only_fields = fields


class StudentAssessmentSerializer(AssessmentSerializer):
    my_result = serializers.SerializerMethodField()

    class Meta(AssessmentSerializer.Meta):
        fields = ("id", "title", "assessment_type", "assessment_type_display", "assessment_date", "max_marks", "pass_marks", "my_result")
        read_only_fields = fields

    def get_my_result(self, assessment):
        result = assessment.results.filter(enrolment=self.context["enrolment"]).first()
        if result is None:
            return None
        return {
            "marks_obtained": float(result.marks_obtained),
            "percentage": result.percentage,
            "result": result.result,
            "remarks": result.remarks,
        }
