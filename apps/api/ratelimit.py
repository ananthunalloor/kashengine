"""Fixed-window rate limits for the API.

The counters live in the Django cache. In production the cache is Redis, so all Gunicorn
workers share the counters. A window is one minute of the clock. A client that passes the limit
gets a 429 answer with `Retry-After`. The counter still grows for each call in the window. A
counter key ends after two windows, so the cache does not fill up.
"""

import time
from dataclasses import dataclass

from django.core.cache import cache

from apps.siteconfig import conf

from .errors import ApiError

WINDOW_SECONDS = 60


@dataclass(frozen=True)
class Window:
    """The state of one rate-limit window after a hit.

    Attributes:
        limit: The most requests in the window.
        remaining: How many requests are left. It is never below zero.
        reset: Seconds until the window ends.
    """

    limit: int
    remaining: int
    reset: int


def _window(now: float | None = None) -> tuple[int, int]:
    """Return the number of the current window and the seconds until it ends.

    Args:
        now: The Unix time. The default is the current time.

    Returns:
        A pair: the number of the window (Unix minutes) and the seconds until the next window
        starts, rounded up and plus one.
    """
    moment = time.time() if now is None else now
    number = int(moment // WINDOW_SECONDS)
    return number, int((number + 1) * WINDOW_SECONDS - moment) + 1


def _count(key: str, number: int) -> int:
    """Add one to the counter of a key in a window. Return the new value.

    The counter ends after two windows. If it ends between the two cache calls, the function
    starts it again at 1.

    Args:
        key: The identity text, for example `token:12`.
        number: The number of the window.

    Returns:
        The count of the key in this window, including this call.
    """
    full_key = f"api:rl:{key}:{number}"
    cache.add(full_key, 0, timeout=WINDOW_SECONDS * 2)
    try:
        return cache.incr(full_key)
    except ValueError:  # The key ended between add and incr.
        cache.set(full_key, 1, timeout=WINDOW_SECONDS * 2)
        return 1


def hit(identity: str, limit: int | None = None, *, now: float | None = None) -> Window:
    """Count one request for an identity and check the limit.

    Args:
        identity: A stable text for the client, for example `token:12` or `user:7`.
        limit: The most requests in a window. The default is `API_RATE_LIMIT_PER_MINUTE`.
        now: The current Unix time. Tests set it.

    Returns:
        The state of the window. Send it to the client as `RateLimit-*` headers.

    Raises:
        ApiError: With code `rate_limited` when the limit is passed. It has `Retry-After`.
    """
    limit = limit or conf.API_RATE_LIMIT_PER_MINUTE
    number, reset = _window(now)
    used = _count(identity, number)
    if used > limit:
        raise ApiError(
            "rate_limited",
            "Too many requests. Wait and try again.",
            headers={
                "Retry-After": str(reset),
                "RateLimit-Limit": str(limit),
                "RateLimit-Remaining": "0",
                "RateLimit-Reset": str(reset),
            },
        )
    return Window(limit=limit, remaining=max(limit - used, 0), reset=reset)


def is_blocked(address: str, *, now: float | None = None) -> bool:
    """Return True if a client address already used all its failed-token checks this minute.

    Args:
        address: The client IP address.
        now: The Unix time. Tests set it.

    Returns:
        True if the failed checks of the address in this window reached
        `API_AUTH_FAIL_LIMIT_PER_MINUTE`.
    """
    number, _reset = _window(now)
    used = cache.get(f"api:rl:fail:{address}:{number}", 0)
    return used >= conf.API_AUTH_FAIL_LIMIT_PER_MINUTE


def record_failure(address: str, *, now: float | None = None) -> None:
    """Count one failed token check for a client address.

    Args:
        address: The client IP address.
        now: The Unix time. Tests set it.
    """
    number, _reset = _window(now)
    _count(f"fail:{address}", number)


def block_response(*, now: float | None = None) -> ApiError:
    """Return the error for an address that has too many failed token checks.

    Args:
        now: The Unix time. Tests set it.

    Returns:
        An `ApiError` with code `rate_limited` and a `Retry-After` header. The caller raises it.
    """
    _number, reset = _window(now)
    return ApiError(
        "rate_limited",
        "Too many failed attempts. Wait and try again.",
        headers={"Retry-After": str(reset)},
    )
