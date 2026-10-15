"""Small view decorators of the web app."""

from collections.abc import Callable
from functools import wraps
from typing import cast

from django.http import HttpResponseNotAllowed
from django.http.response import HttpResponseBase


def post_only[View: Callable[..., HttpResponseBase]](view: View) -> View:
    """Allow POST requests only. Any other method gets a 405 page.

    This is the same rule as Django `require_POST`. It keeps the type of the view, so the type
    checker accepts the view in a URL list.

    Args:
        view: The view function.

    Returns:
        The wrapped view.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        return view(request, *args, **kwargs)

    return cast("View", wrapper)
