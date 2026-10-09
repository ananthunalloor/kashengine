"""Access rules for the Ops pages.

Staff users may look at the pages. Only superusers may change something: start a job, end a
session, or turn a user on or off. Anonymous users are sent to the login by the middleware.
"""

from collections.abc import Callable
from functools import wraps
from typing import cast

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.http.response import HttpResponseBase


def staff_required[View: Callable[..., HttpResponseBase]](view: View) -> View:
    """Allow staff users only. Others get a 403 page."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return cast("View", wrapper)


def superuser_required[View: Callable[..., HttpResponseBase]](view: View) -> View:
    """Allow superusers only. Others get a 403 page."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return cast("View", wrapper)


def superuser_post_required[View: Callable[..., HttpResponseBase]](view: View) -> View:
    """Allow POST requests from superusers only. A GET request gets a 405 page."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return cast("View", wrapper)
