from django.urls import path
from courses.views import api_views

app_name = "courses_api"


urlpatterns = [
    path("categories/", api_views.category_list, name="category_list"),                                                 # GET
    path("courses/", api_views.course_list, name="course_list"),                                                        # GET
    path("courses/<int:course_id>/", api_views.course_detail, name="course_detail"),                                    # GET
    path("courses/<slug:slug>/", api_views.course_detail, name="course_detail_by_slug"),                                # GET
    path("faculty/", api_views.faculty_list, name="faculty_list"),                                                      # GET
    path("faculty/<uuid:user_id>/", api_views.faculty_detail, name="faculty_detail"),                                   # GET

    # ADMIN
    path("admin/categories/", api_views.admin_category_list_create, name="admin_category_list_create"),                 # GET, POST
    path("admin/categories/<int:category_id>/", api_views.admin_category_detail, name="admin_category_detail"),         # GET, PATCH, DELETE
    path("admin/courses/", api_views.admin_course_list_create, name="admin_course_list_create"),                        # GET, POST
    path("admin/courses/<int:course_id>/", api_views.admin_course_detail, name="admin_course_detail"),                  # GET, PATCH, DELETE
]