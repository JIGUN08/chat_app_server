#asgi.py 

import os

import django
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
import api.routing
from api.middleware import TokenAuthMiddleware 

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app_server.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    
    # 💡 WebSocket 요청에 TokenAuthMiddleware 적용
    "websocket":TokenAuthMiddleware(
        URLRouter( 
            api.routing.websocket_urlpatterns
        )
    )
})
