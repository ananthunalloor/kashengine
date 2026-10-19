"""React read routes retain canonical Ops names without exposing legacy POST handlers."""

from django.urls import path

from apps.api.app.ops_pages import PAGES
from apps.web import views

from .permissions import staff_required, superuser_required
from .urls import urlpatterns as legacy_patterns

app_name = "ops"

urlpatterns = [
    path(
        str(pattern.pattern),
        (superuser_required if pattern.name == "backups" else staff_required)(
            views.react_ops_run if pattern.name == "run" else views.react_ops_page
        ),
        name=pattern.name,
    )
    for pattern in legacy_patterns
    if pattern.name in PAGES | {"runs", "run", "audit"}
]
