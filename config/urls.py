"""Root URL configuration."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def health(request):
    """Used by Docker health checks."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
]
