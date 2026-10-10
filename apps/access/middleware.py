"""The access check for the web pages.

It runs after the login check. It looks at the name of the URL, so a page cannot skip the rules.
The Ops pages and the admin site have their own rules (staff only), so they are not checked here.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from . import features
from .rules import Access

DATASTAR_HEADER = "Datastar-Request"


def access_for(request: HttpRequest) -> Access:
    """The `Access` object of the request. It is made once for each request."""
    existing = getattr(request, "access", None)
    if existing is None:
        existing = Access(request.user)
        request.access = existing  # ty: ignore[unresolved-attribute]
    return existing


def _refuse(request: HttpRequest, template: str, context: dict) -> HttpResponse:
    """A 403 page. A Datastar request gets a short text, so the page does not break."""
    if request.headers.get(DATASTAR_HEADER):
        return HttpResponse("Not allowed.", status=403, content_type="text/plain")
    return render(request, template, context, status=403)


class AccessMiddleware:
    """Check the feature and the subscription before a web view runs."""

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Pass the request on. The checks are in `process_view`."""
        return self.get_response(request)

    def process_view(self, request: HttpRequest, view_func, view_args, view_kwargs):
        """Return a refusal, or None to let the view run."""
        match = request.resolver_match
        if match is None or match.namespace != "web" or not request.user.is_authenticated:
            return None
        name = match.url_name
        if name in features.OPEN_URL_NAMES:
            return None
        access = access_for(request)
        if not access.subscription_ok:
            if request.headers.get(DATASTAR_HEADER):
                return _refuse(request, "", {})
            return redirect(reverse("web:account"))
        feature = features.BY_URL_NAME.get(name or "")
        if feature and not access.can(feature.key):
            return _refuse(request, "web/no_access.html", {"feature": feature})
        return None
