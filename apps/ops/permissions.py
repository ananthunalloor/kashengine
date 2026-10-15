"""Access rules for the Ops pages.

Staff users may look at the pages. Only superusers may change something: start a job, end a
session, or turn a user on or off. Anonymous users are sent to the login by the middleware.

The three decorators in this module wrap the view functions in `views.py`, `views_access.py`,
and `views_settings.py`. Each decorator keeps the type of the view it wraps. A user who fails a
check gets the Django 403 page (`PermissionDenied`). The decorators do not write to the audit
trail.
"""

from collections.abc import Callable
from functools import wraps
from typing import cast

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.http.response import HttpResponseBase


def staff_required[View: Callable[..., HttpResponseBase]](view: View) -> View:
    """Wrap a view so that only staff users can call it.

    The wrapper reads `request.user.is_staff`. A superuser is normally also staff. The wrapper
    allows any HTTP method.

    Args:
        view: The view function to protect. Its first parameter is the request.

    Returns:
        A function with the same signature as `view`.

    Note:
        The returned wrapper raises `PermissionDenied` (a 403 page) for a user who is not staff.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        """Call the view for a staff user. Raise `PermissionDenied` for any other user."""
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return cast("View", wrapper)


def superuser_required[View: Callable[..., HttpResponseBase]](view: View) -> View:
    """Wrap a view so that only superusers can call it.

    The wrapper reads `request.user.is_superuser`. A staff user who is not a superuser gets a
    403 page. The wrapper allows any HTTP method.

    Args:
        view: The view function to protect. Its first parameter is the request.

    Returns:
        A function with the same signature as `view`.

    Note:
        The returned wrapper raises `PermissionDenied` (a 403 page) for a user who is not a
        superuser.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        """Call the view for a superuser. Raise `PermissionDenied` for any other user."""
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return cast("View", wrapper)


def superuser_post_required[View: Callable[..., HttpResponseBase]](view: View) -> View:
    """Wrap a view so that only a POST request from a superuser can call it.

    The wrapper checks the HTTP method first. Any method other than POST gets a 405 response
    that lists POST as the allowed method. This holds for every user, also for a user who is
    not a superuser. Then the wrapper checks `request.user.is_superuser`.

    Args:
        view: The view function to protect. Its first parameter is the request.

    Returns:
        A function with the same signature as `view`.

    Note:
        The returned wrapper raises `PermissionDenied` (a 403 page) for a POST request from a
        user who is not a superuser. The CSRF middleware still checks the POST request.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        """Return a 405 response for a non-POST request. Reject a user who is not a superuser."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return cast("View", wrapper)
