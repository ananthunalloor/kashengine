"""ASGI config: Django HTTP plus the live-quote WebSocket (Django Channels).

The `realtime` Compose service runs this application with Uvicorn. Caddy sends only `/ws/*` to it;
every other path still goes to the WSGI `web` service (Gunicorn), whose server-sent event streams
need a synchronous server.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

django_application = get_asgi_application()

# Import after Django is set up: the routes import models.
from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.markets.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_application,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
