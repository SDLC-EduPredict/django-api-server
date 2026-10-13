from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination


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


def paginated_response(request, queryset, serializer_class, message):
    paginator = PageNumberPagination()
    paginator.page_size_query_param = "page_size"
    paginator.max_page_size = 100
    page = paginator.paginate_queryset(queryset, request)
    results = serializer_class(page, many=True, context={"request": request}).data
    return success_response(message, paginator.get_paginated_response(results).data)