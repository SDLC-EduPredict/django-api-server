from assessments.models import Assessment
from enrolments.utils import average


def assessment_summary(enrolment) -> dict:
    results = list(enrolment.assessment_results.select_related("assessment"))
    mock_tests = [result.percentage for result in results if result.assessment.assessment_type == Assessment.Type.MOCK_TEST]
    exams = [result.percentage for result in results if result.assessment.assessment_type == Assessment.Type.EXAM]
    return {
        "total_assessments": Assessment.objects.filter(course=enrolment.course).count(),
        "attempted": len(results),
        "passed": len([result for result in results if result.result == "PASS"]),
        "mock_test_average": average(mock_tests),
        "exam_average": average(exams),
        "assessment_average": average(mock_tests + exams),
    }
