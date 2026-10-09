"""Facts about a web request: the client address and the browser."""

import ipaddress

from django.http import HttpRequest

MAX_USER_AGENT_CHARS = 300


def client_ip(request: HttpRequest | None) -> str | None:
    """The address of the client.

    Behind Caddy, the first value of X-Forwarded-For is the client. Caddy replaces the header
    that a client sends, and the web container has no other way in, so the value is safe.
    """
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None  # A bad header must not break a login.


def user_agent(request: HttpRequest | None) -> str:
    """The browser name, cut to a safe length."""
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:MAX_USER_AGENT_CHARS]
