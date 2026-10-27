"""WebSocket routes of the ASGI `realtime` service."""

from django.urls import path

from .consumers import LiveQuotesConsumer

websocket_urlpatterns = [
    path("ws/live/quotes/", LiveQuotesConsumer.as_asgi()),
]
