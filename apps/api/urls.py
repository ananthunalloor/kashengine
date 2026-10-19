"""URL routes of the API. They are mounted at `/api/`.

Each major version has its own `NinjaAPI` object, so `v2` can be added next to `v1`.
The session-only `/api/app/` API is private and is not part of the public version contract.
"""

from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, JsonResponse
from django.urls import URLPattern, URLResolver, include, path

from . import docs
from .app.api import api as api_app
from .v1.api import api as api_v1
from .versions import CURRENT, VERSIONS


@login_not_required
def discovery(request: HttpRequest) -> JsonResponse:
    """List the API versions. It needs no sign-in.

    Args:
        request: The request. The function does not read it.

    Returns:
        A JSON object with each version, its status, and the links to its pages.
    """
    items = [
        {
            "version": version.major,
            "contract": version.semver,
            "status": version.status,
            "url": f"/api/{version.major}/",
            "openapi": f"/api/{version.major}/openapi.json",
            "docs": f"/api/{version.major}/docs",
            "sunset": version.sunset_on or None,
        }
        for version in VERSIONS.values()
    ]
    return JsonResponse({"current": CURRENT, "versions": items})


def _without_login_redirect(patterns: list) -> list:
    """Mark the ninja views as `login_not_required`. The API answers 401 itself.

    The login middleware of the project redirects an anonymous user to the login page. An API
    client needs a `401` answer, so the API checks the caller in its own auth classes.

    Args:
        patterns: The URL patterns of the ninja API. Nested resolvers are included.

    Returns:
        The same list. The function changes the callbacks in place.
    """
    for pattern in patterns:
        if isinstance(pattern, URLPattern):
            pattern.callback = login_not_required(pattern.callback)
        elif isinstance(pattern, URLResolver):
            _without_login_redirect(pattern.url_patterns)
    return patterns


_v1_patterns, _v1_app, _v1_namespace = api_v1.urls
_without_login_redirect(_v1_patterns)
_app_patterns, _app_app, _app_namespace = api_app.urls
_without_login_redirect(_app_patterns)

urlpatterns = [
    path("", discovery, name="discovery"),
    path("v1/docs", docs.swagger, name="docs"),
    path("v1/", include((_v1_patterns, _v1_app), namespace=_v1_namespace)),
    path("app/", include((_app_patterns, _app_app), namespace=_app_namespace)),
]
