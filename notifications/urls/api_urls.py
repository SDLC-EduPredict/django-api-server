from django.urls import path
from notifications.views import api_views

app_name = "notifications_api"


urlpatterns = [
    path("notifications/", api_views.notification_list, name="notification_list"),                                                          # 
    path("notifications/unread-count/", api_views.notification_unread_count, name="notification_unread_count"),                             # 
    path("notifications/read-all/", api_views.notification_mark_all_read, name="notification_mark_all_read"),                               # 
    path("notifications/<int:notification_id>/", api_views.notification_detail, name="notification_detail"),                                # 
    path("notifications/<int:notification_id>/read/", api_views.notification_mark_read, name="notification_mark_read"),                     # 

    path("admin/notifications/", api_views.admin_notification_list_send, name="admin_notification_list_send"),                              # 
    path("admin/notifications/<int:notification_id>/", api_views.admin_notification_delete, name="admin_notification_delete"),              # 
]