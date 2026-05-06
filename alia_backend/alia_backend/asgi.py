import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from api.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alia_backend.settings')

application = ProtocolTypeRouter({
    'http':      get_asgi_application(),
    'websocket': URLRouter(websocket_urlpatterns),
})
