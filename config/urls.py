"""Root URL configuration."""

from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse
from django.urls import include, path, re_path

from apps.delivery.views import telegram_webhook
from apps.web.public_preview import page_not_found

handler403 = "apps.web.public_preview.permission_denied"
handler404 = "apps.web.public_preview.page_not_found"


@login_not_required
def health(request):
    """Used by Docker health checks."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/telegram/webhook/", telegram_webhook, name="telegram_webhook"),
    path("api/", include("apps.api.urls")),
    path("ops/", include("apps.ops.react_urls")),
    path("", include("apps.web.urls")),
    re_path(r"^(?!api/).*$", page_not_found),
]
