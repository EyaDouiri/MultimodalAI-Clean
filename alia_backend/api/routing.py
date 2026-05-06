from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/sim/(?P<user_id>\d+)/$', consumers.SimConsumer.as_asgi()),
]
