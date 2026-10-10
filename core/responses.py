from rest_framework.response import Response


def success_response(message, data=None, status_code=200):
    return Response({
        "status": "success",
        "status_code": status_code,
        "message": message,
        "data": data,
        "errors": None,
    }, status=status_code)


def error_response(message, errors=None, status_code=400):
    return Response({
        "status": "error",
        "status_code": status_code,
        "message": message,
        "data": None,
        "errors": errors,
    }, status=status_code)