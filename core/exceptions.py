from rest_framework.views import exception_handler
from core.responses import error_response


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None

    data = response.data
    if isinstance(data, dict) and "detail" in data:
        return error_response(str(data["detail"]), None, response.status_code)
    return error_response("Request failed.", data, response.status_code)