"""Hooks for django-axes. They read the limits from the dashboard settings."""

import math
from datetime import timedelta

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.ops.requestinfo import client_ip as validated_client_ip
from apps.web.public_preview import preview_response

from . import conf


def failure_limit(request: HttpRequest, credentials: dict | None) -> int:
    """Return the failed logins that start a lockout.

    django-axes calls this function (`AXES_FAILURE_LIMIT`). The limit is a dashboard setting.

    Args:
        request: The login request. The function does not use it.
        credentials: The credentials of the login. The function does not use them.

    Returns:
        The value of `LOGIN_FAILURE_LIMIT`.
    """
    return int(conf.LOGIN_FAILURE_LIMIT)


def cooloff(request: HttpRequest | None) -> timedelta | None:
    """Return the lockout time.

    Args:
        request: The login request. The function does not use it.

    Returns:
        A `timedelta` of `LOGIN_COOLOFF_MINUTES` minutes. None if the setting is 0: the address
        stays locked until an admin unlocks it.
    """
    minutes = int(conf.LOGIN_COOLOFF_MINUTES)
    return timedelta(minutes=minutes) if minutes else None


def client_ip(request: HttpRequest) -> str | None:
    """Return the client address. Behind Caddy it is the first value of X-Forwarded-For.

    Args:
        request: The login request.

    Returns:
        The address as text. If the header is not a valid address, the connection address.
        None if the request has no valid address.
    """
    return validated_client_ip(request) or request.META.get("REMOTE_ADDR")


def lockout(
    request: HttpRequest, response: HttpResponse | None = None, credentials: dict | None = None
) -> HttpResponse:
    """Return the page for a locked-out address. It tells nothing about users or limits.

    Args:
        request: The login request.
        response: The response that django-axes made. The function does not use it.
        credentials: The credentials of the login. The function does not use them.

    Returns:
        A `429` response that shows the template `web/locked_out.html`. The page shows the
        minutes to wait, rounded up, if the lockout ends by time.
    """
    wait = cooloff(request)
    minutes = math.ceil(wait.total_seconds() / 60) if wait else None
    if not request.path.startswith("/admin/"):
        return preview_response(request, page="lockout", status=429, minutes=minutes)
    return render(request, "web/locked_out.html", {"minutes": minutes}, status=429)
