"""The access check for the web pages.

It runs after the login check. It looks at the name of the URL, so a page cannot skip the rules.
The Ops pages and the admin site have their own rules (staff only), so they are not checked here.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.web.public_preview import preview_response

from . import features
from .rules import Access

DATASTAR_HEADER = "Datastar-Request"


def access_for(request: HttpRequest) -> Access:
    """Return the `Access` object of the request. It is made once for each request.

    The function saves the object on `request.access`. Later calls in the same request use it,
    so the database is read only one time.

    Args:
        request: The request. `request.user` must be set.

    Returns:
        The access rules for `request.user`.
    """
    existing = getattr(request, "access", None)
    if existing is None:
        existing = Access(request.user)
        request.access = existing  # ty: ignore[unresolved-attribute]
    return existing


def _refuse(request: HttpRequest, template: str, context: dict) -> HttpResponse:
    """Return a 403 answer. A Datastar request gets a short text, so the page does not break.

    Args:
        request: The request.
        template: The template of the 403 page.
        context: The context of the template.

    Returns:
        A response with status 403. It is plain text for a Datastar request, else the page.
    """
    if request.headers.get(DATASTAR_HEADER):
        return HttpResponse("Not allowed.", status=403, content_type="text/plain")
    if not getattr(request, "is_archive", False):
        return preview_response(
            request, page="access", status=403, feature=context["feature"].label
        )
    return render(request, template, context, status=403)


class AccessMiddleware:
    """Check the feature and the subscription before a web view runs."""

    def __init__(self, get_response) -> None:
        """Save the next handler of the middleware chain."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Pass the request on. The checks are in `process_view`."""
        return self.get_response(request)

    def process_view(self, request: HttpRequest, view_func, view_args, view_kwargs):
        """Return a refusal, or None to let the view run.

        The check applies only to the views in the `web` namespace and only to signed-in users.
        A URL name in `OPEN_URL_NAMES` (dashboard, account, login, logout) is always allowed.
        If the subscription rule fails, the user goes to the account page (a Datastar request
        gets a 403 text). If the page belongs to a feature that the user may not use, the user
        gets the 403 page `web/no_access.html`.

        Args:
            request: The request. The resolved URL of the request decides the check.
            view_func: The view that Django will call. The method does not use it.
            view_args: The positional arguments of the view. The method does not use them.
            view_kwargs: The keyword arguments of the view. The method does not use them.

        Returns:
            A response to send instead of the view, or None to let the view run.
        """
        match = request.resolver_match
        if match is None or match.namespace != "web" or not request.user.is_authenticated:
            return None
        name = match.url_name
        if name in features.OPEN_URL_NAMES:
            return None
        access = access_for(request)
        if not access.email_verified or not access.subscription_ok:
            if request.headers.get(DATASTAR_HEADER):
                return HttpResponse(
                    "Verify your email in Account settings to unlock all features."
                    if not access.email_verified
                    else "Not allowed.",
                    status=403,
                    content_type="text/plain",
                )
            return redirect(reverse("web:account"))
        feature = features.BY_URL_NAME.get(name or "")
        if feature and not access.can(feature.key):
            return _refuse(request, "web/no_access.html", {"feature": feature})
        return None
