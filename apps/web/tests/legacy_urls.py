"""Isolated URLconf for unit tests of archived renderers and domain actions.

Deployed hostname and role authorization are exercised separately in test_archive.
"""

from django.contrib import admin
from django.urls import include, path

from config.urls import health

urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("ops/", include("apps.ops.urls")),
    path("", include("apps.web.legacy_urls")),
]


class LegacyRendererContext:
    """Supply archive presentation context without replacing domain permission checks."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.is_archive = True
        return self.get_response(request)
