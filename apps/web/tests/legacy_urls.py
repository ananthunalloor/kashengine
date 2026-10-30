"""Isolated URLconf for tests of legacy renderers and domain actions.

Canonical routes are tested separately from legacy views.
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
