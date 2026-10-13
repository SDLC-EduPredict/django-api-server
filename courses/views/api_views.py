import logging

from django.db.models import Count, ProtectedError, Q
from rest_framework import status
from rest_framework.decorators import api_view

from accounts.decorators import jwt_required
from accounts.forms import with_current_values
from accounts.models import User
from core.responses import error_response, paginated_response, success_response
from courses.forms import CourseCategoryForm, CourseFilterForm, CourseForm
from courses.models import Course, CourseCategory
from courses.serializers import CourseCategorySerializer, CourseDetailSerializer, CourseListSerializer, FacultyListSerializer
from permissions.constants import ADD_COURSE, DELETE_COURSE, EDIT_COURSE, MANAGE_CATEGORIES
from permissions.decorators import permission_required

logger = logging.getLogger(__name__)


def all_courses():
    return Course.objects.select_related("category", "faculty__faculty_profile")


def published_courses():
    return all_courses().filter(status=Course.Status.PUBLISHED, category__is_active=True)


def active_faculty():
    published = Q(courses_taught__status=Course.Status.PUBLISHED, courses_taught__category__is_active=True)
    return (User.objects
            .select_related("faculty_profile")
            .filter(role=User.Role.FACULTY, is_active=True)
            .annotate(course_count=Count("courses_taught", filter=published))
            .order_by("first_name", "last_name"))


def categories_with_course_count():
    return CourseCategory.objects.annotate(course_count=Count("courses"))


def filter_courses(courses, filters):
    for word in filters["search"].split():
        courses = courses.filter(
            Q(title__icontains=word) | Q(short_description__icontains=word) | Q(description__icontains=word)
            | Q(category__name__icontains=word) | Q(faculty__first_name__icontains=word)
            | Q(faculty__last_name__icontains=word))

    category = filters["category"]
    if category:
        courses = courses.filter(category_id=category) if category.isdigit() else courses.filter(category__slug=category)
    if filters["level"]:
        courses = courses.filter(level=filters["level"])
    if filters["mode"]:
        courses = courses.filter(mode=filters["mode"])
    if filters["status"]:
        courses = courses.filter(status=filters["status"])
    if filters["faculty"]:
        courses = courses.filter(faculty_id=filters["faculty"])
    if filters["min_fee"] is not None:
        courses = courses.filter(fee__gte=filters["min_fee"])
    if filters["max_fee"] is not None:
        courses = courses.filter(fee__lte=filters["max_fee"])
    return courses.order_by(filters["ordering"] or "-created_at", "id")


@api_view(["GET"])
def category_list(request):
    published = Q(courses__status=Course.Status.PUBLISHED)
    categories = CourseCategory.objects.filter(is_active=True).annotate(course_count=Count("courses", filter=published))
    data = CourseCategorySerializer(categories, many=True).data
    return success_response("Course categories fetched successfully.", {"categories": data})


@api_view(["GET"])
def course_list(request):
    form = CourseFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid search or filter values.", form.errors)

    courses = filter_courses(published_courses(), form.cleaned_data)
    return paginated_response(request, courses, CourseListSerializer, "Courses fetched successfully.")


@api_view(["GET"])
def course_detail(request, course_id=None, slug=None):
    courses = published_courses()
    course = courses.filter(pk=course_id).first() if course_id else courses.filter(slug=slug).first()

    if course is None:
        return error_response("Course not found.", status_code=status.HTTP_404_NOT_FOUND)

    data = CourseDetailSerializer(course, context={"request": request}).data
    return success_response("Course fetched successfully.", {"course": data})


@api_view(["GET"])
def faculty_list(request):
    faculty = active_faculty()
    for word in request.query_params.get("search", "").split():
        faculty = faculty.filter(
            Q(first_name__icontains=word) | Q(last_name__icontains=word)
            | Q(faculty_profile__designation__icontains=word) | Q(faculty_profile__expertise__icontains=word))
    return paginated_response(request, faculty, FacultyListSerializer, "Faculty fetched successfully.")


@api_view(["GET"])
def faculty_detail(request, user_id):
    faculty = active_faculty().filter(pk=user_id).first()
    if faculty is None:
        return error_response("Faculty member not found.", status_code=status.HTTP_404_NOT_FOUND)

    courses = published_courses().filter(faculty=faculty)
    return success_response("Faculty member fetched successfully.", {
        "faculty": FacultyListSerializer(faculty, context={"request": request}).data,
        "courses": CourseListSerializer(courses, many=True, context={"request": request}).data
    })


@api_view(["GET", "POST"])
@jwt_required
@permission_required(MANAGE_CATEGORIES)
def admin_category_list_create(request):
    if request.method == "GET":
        categories = categories_with_course_count()
        search = request.query_params.get("search")
        if search:
            categories = categories.filter(name__icontains=search)
        data = CourseCategorySerializer(categories, many=True).data
        return success_response("Course categories fetched successfully.", {"categories": data})

    form = CourseCategoryForm(request.data)
    if not form.is_valid():
        return error_response("Category creation failed.", form.errors)

    category = form.save()
    logger.info("Category '%s' created by %s", category.name, request.user.email)
    data = CourseCategorySerializer(categories_with_course_count().get(pk=category.pk)).data
    return success_response("Category created successfully!", {"category": data}, status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@jwt_required
@permission_required(MANAGE_CATEGORIES)
def admin_category_detail(request, category_id):
    category = categories_with_course_count().filter(pk=category_id).first()
    if category is None:
        return error_response("Category not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return success_response("Category fetched successfully.", {"category": CourseCategorySerializer(category).data})

    if request.method == "PATCH":
        form = CourseCategoryForm(with_current_values(category, CourseCategoryForm, request.data), instance=category)
        if not form.is_valid():
            return error_response("Category update failed.", form.errors)

        form.save()
        logger.info("Category '%s' updated by %s", category.name, request.user.email)
        data = CourseCategorySerializer(categories_with_course_count().get(pk=category.pk)).data
        return success_response("Category updated successfully!", {"category": data})

    try:
        category.delete()
    except ProtectedError:
        return error_response("This category still has courses. Move those courses to another category or delete them first.")

    logger.info("Category '%s' deleted by %s", category.name, request.user.email)
    return success_response("Category deleted successfully!")


@api_view(["GET", "POST"])
@jwt_required
def admin_course_list_create(request):
    if request.method == "GET":
        return list_all_courses(request)
    return create_course(request)


@permission_required(EDIT_COURSE)
def list_all_courses(request):
    form = CourseFilterForm(request.query_params)
    if not form.is_valid():
        return error_response("Invalid search or filter values.", form.errors)

    courses = filter_courses(all_courses(), form.cleaned_data)
    return paginated_response(request, courses, CourseListSerializer, "Courses fetched successfully.")


@permission_required(ADD_COURSE)
def create_course(request):
    form = CourseForm(request.data, request.FILES)
    if not form.is_valid():
        return error_response("Course creation failed.", form.errors)

    course = form.save()
    logger.info("Course '%s' created by %s", course.title, request.user.email)
    data = CourseDetailSerializer(course, context={"request": request}).data
    return success_response("Course created successfully!", {"course": data}, status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@jwt_required
def admin_course_detail(request, course_id):
    course = all_courses().filter(pk=course_id).first()
    if course is None:
        return error_response("Course not found.", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return show_course(request, course)
    if request.method == "PATCH":
        return update_course(request, course)
    return delete_course(request, course)


@permission_required(EDIT_COURSE)
def show_course(request, course):
    data = CourseDetailSerializer(course, context={"request": request}).data
    return success_response("Course fetched successfully.", {"course": data})


@permission_required(EDIT_COURSE)
def update_course(request, course):
    form = CourseForm(with_current_values(course, CourseForm, request.data), request.FILES, instance=course)
    if not form.is_valid():
        return error_response("Course update failed.", form.errors)

    course = form.save()
    logger.info("Course '%s' updated by %s", course.title, request.user.email)
    data = CourseDetailSerializer(course, context={"request": request}).data
    return success_response("Course updated successfully!", {"course": data})


@permission_required(DELETE_COURSE)
def delete_course(request, course):
    try:
        course.delete()
    except ProtectedError:
        return error_response("This course has enrolments, so it cannot be deleted. Set its status to ARCHIVED instead.")

    logger.info("Course '%s' deleted by %s", course.title, request.user.email)
    return success_response("Course deleted successfully!")