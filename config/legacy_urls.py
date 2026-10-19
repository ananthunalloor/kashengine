"""Host-isolated archived Django pages and their original action handlers."""

from django.urls import include, path, re_path

from apps.web.archive import ArchiveLogin, archive_not_found

handler403 = "apps.web.public_preview.permission_denied"
handler404 = "apps.web.archive.archive_not_found"

urlpatterns = [
    path("login/", ArchiveLogin.as_view(), name="archive_login"),
    path("ops/", include("apps.ops.urls")),
    path("", include("apps.web.legacy_urls")),
    re_path(r"^.*$", archive_not_found),
]
