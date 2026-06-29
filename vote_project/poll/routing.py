from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/election/$', consumers.ElectionConsumer.as_asgi()),
    re_path(r'ws/staff/$', consumers.ElectoralStaffConsumer.as_asgi()),
]