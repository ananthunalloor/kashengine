"""Facts about a web request: the client address and the browser."""

import ipaddress

from django.http import HttpRequest

MAX_USER_AGENT_CHARS = 300


def client_ip(request: HttpRequest | None) -> str | None:
    """Return the address of the client of a request.

    Behind Caddy, the first value of X-Forwarded-For is the client. Caddy replaces the header
    that a client sends, and the web container has no other way in, so the value is safe. Without
    the header, the function uses `REMOTE_ADDR`. It checks that the text is an IP address.

    Args:
        request: The web request. It can be `None`, for example in a task.

    Returns:
        The address as normal text (IPv6 in short form). `None` if the request is `None`, or if the
        value is empty or is not an IP address.

    Security:
        The function trusts the first value of X-Forwarded-For. This is safe only behind the
        proxy. Without the proxy, a client can set any address.
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
    """Return the User-Agent header of a request, cut to a safe length.

    Args:
        request: The web request. It can be `None`.

    Returns:
        The header text, cut to `MAX_USER_AGENT_CHARS` characters. An empty text if the request is
        `None` or has no header.
    """
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:MAX_USER_AGENT_CHARS]
