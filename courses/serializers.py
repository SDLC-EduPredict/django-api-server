from rest_framework import serializers
from accounts.models import User
from courses.models import Course, CourseCategory


class CourseCategorySerializer(serializers.ModelSerializer):
    course_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CourseCategory
        fields = ("id", "name", "slug", "description", "is_active", "course_count", "created_at", "updated_at")
        read_only_fields = fields


class CategoryShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseCategory
        fields = ("id", "name", "slug")
        read_only_fields = fields


class FacultySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    designation = serializers.CharField(source="faculty_profile.designation", read_only=True, default="")
    expertise = serializers.CharField(source="faculty_profile.expertise", read_only=True, default="")
    bio = serializers.CharField(source="faculty_profile.bio", read_only=True, default="")
    photo = serializers.ImageField(source="faculty_profile.photo", read_only=True, default=None)

    class Meta:
        model = User
        fields = ("id", "full_name", "designation", "expertise", "bio", "photo")
        read_only_fields = fields


class FacultyListSerializer(FacultySerializer):
    course_count = serializers.IntegerField(read_only=True)

    class Meta(FacultySerializer.Meta):
        fields = FacultySerializer.Meta.fields + ("course_count",)
        read_only_fields = fields


class CourseListSerializer(serializers.ModelSerializer):
    category = CategoryShortSerializer(read_only=True)
    faculty = FacultySerializer(read_only=True)
    level_display = serializers.CharField(source="get_level_display", read_only=True)
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    fee = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False, read_only=True)

    class Meta:
        model = Course
        fields = (
            "id", "title", "slug", "short_description", "category", "faculty", "level", "level_display",
            "mode", "mode_display", "duration_weeks", "total_modules", "fee", "start_date", "thumbnail",
            "status", "status_display")
        read_only_fields = fields


class CourseDetailSerializer(CourseListSerializer):
    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + ("description", "meta_title", "meta_description", "created_at", "updated_at")
        read_only_fields = fields