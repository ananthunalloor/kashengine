"""Root URL configuration."""

from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse
from django.urls import include, path

handler403 = "apps.web.public_preview.permission_denied"


@login_not_required
def health(request):
    """Used by Docker health checks."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/", include("apps.api.urls")),
    path("ops/", include("apps.ops.urls")),
    path("", include("apps.web.urls")),
]
