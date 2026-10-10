"""Hooks for django-axes. They read the limits from the dashboard settings."""

import math
from datetime import timedelta

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.ops.requestinfo import client_ip as validated_client_ip

from . import conf


def failure_limit(request: HttpRequest, credentials: dict | None) -> int:
    """Failed logins before a lockout."""
    return int(conf.LOGIN_FAILURE_LIMIT)


def cooloff(request: HttpRequest | None) -> timedelta | None:
    """The lockout time. None means: until an admin unlocks the address."""
    minutes = int(conf.LOGIN_COOLOFF_MINUTES)
    return timedelta(minutes=minutes) if minutes else None


def client_ip(request: HttpRequest) -> str | None:
    """The client address. Behind Caddy it is the first value of X-Forwarded-For."""
    return validated_client_ip(request) or request.META.get("REMOTE_ADDR")


def lockout(
    request: HttpRequest, response: HttpResponse | None = None, credentials: dict | None = None
) -> HttpResponse:
    """The page for a locked-out address. It tells nothing about users or limits."""
    wait = cooloff(request)
    minutes = math.ceil(wait.total_seconds() / 60) if wait else None
    return render(request, "web/locked_out.html", {"minutes": minutes}, status=429)
