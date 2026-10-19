"""Middleware for the `/api/` paths.

It does four things for a request below `/api/`:

1. If an admin turned the API off, it answers 503 before any view runs.
2. It adds `API-Version`, the rate-limit headers and, for a deprecated version, the
   `Deprecation`, `Sunset` and `Link` headers.
3. It marks every answer as private. Answers depend on the caller.
4. It adds an `ETag` to JSON answers and answers 304 when the client already has the same data.

The private `/api/app/` uses its own session auth and request budget. It is independent of the
public API switch and version headers, and its responses are always private and no-store.
It does nothing for paths outside `/api/`.
"""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import format_datetime

from django.http import HttpRequest, HttpResponse

from apps.siteconfig import conf

from . import versions
from .errors import problem

API_PREFIX = "/api/"


def _version_of(path: str) -> versions.Version | None:
    """Return the API version in a path like `/api/v1/news`, or None.

    Args:
        path: The path of the request.

    Returns:
        The version object, or None if the path has no known version, for example `/api/`.
    """
    parts = path.removeprefix(API_PREFIX).split("/", 1)
    return versions.VERSIONS.get(parts[0])


def _deprecation_headers(version: versions.Version) -> dict[str, str]:
    """Return the headers for a deprecated or retired version (RFC 8594).

    Args:
        version: The API version of the request.

    Returns:
        An empty dict for a stable version. For other versions: `Deprecation`, and `Sunset` and
        `Link` (to the successor) when the version has a sunset date or a successor.
    """
    headers: dict[str, str] = {}
    if version.status == "stable":
        return headers
    headers["Deprecation"] = (
        f"@{_epoch(version.deprecated_on)}" if version.deprecated_on else "true"
    )
    if version.sunset_on:
        headers["Sunset"] = _http_date(version.sunset_on)
    if version.successor:
        headers["Link"] = f'</api/{version.successor}/>; rel="successor-version"'
    return headers


def _epoch(day: str) -> int:
    """Return a `YYYY-MM-DD` day as Unix seconds (00:00 UTC).

    Args:
        day: The date in ISO format.

    Returns:
        The Unix time of the start of that day in UTC.
    """
    return int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp())


def _http_date(day: str) -> str:
    """Return a `YYYY-MM-DD` day as an HTTP date (RFC 9110).

    Args:
        day: The date in ISO format.

    Returns:
        The start of that day in UTC, for example `Wed, 01 Jan 2031 00:00:00 GMT`.
    """
    return format_datetime(datetime.fromisoformat(day).replace(tzinfo=UTC), usegmt=True)


class ApiMiddleware:
    """Apply the API rules to every request below `/api/`."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Save the next handler."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Handle one request."""
        if not request.path.startswith(API_PREFIX):
            return self.get_response(request)
        version = _version_of(request.path)
        is_app = request.path.startswith("/api/app/")
        if not is_app and not conf.API_ENABLED:
            response = problem(request, "api_disabled", "The API is turned off.")
            response["Retry-After"] = "300"
        else:
            response = self.get_response(request)
        self._add_headers(request, response, version)
        if is_app:
            response["Cache-Control"] = "private, no-store"
            return response
        return self._conditional(request, response)

    @staticmethod
    def _add_headers(
        request: HttpRequest, response: HttpResponse, version: versions.Version | None
    ) -> None:
        """Add the version, rate-limit and cache headers to a response.

        The method changes the response. `RateLimit-*` headers are set only when the request has
        a rate-limit window and the response has no such header yet (a `429` answer has its own).
        `Vary` always includes `Authorization` and `Cookie`.

        Args:
            request: The request. `request.api_rate` is the window that the auth code set.
            response: The response to change.
            version: The API version of the path, or None.
        """
        if version is not None:
            response["API-Version"] = version.semver
            for name, value in _deprecation_headers(version).items():
                response[name] = value
        window = getattr(request, "api_rate", None)
        if window is not None and "RateLimit-Limit" not in response:
            response["RateLimit-Limit"] = str(window.limit)
            response["RateLimit-Remaining"] = str(window.remaining)
            response["RateLimit-Reset"] = str(window.reset)
            response["RateLimit-Policy"] = f"{window.limit};w=60"
        response["Vary"] = ", ".join(
            dict.fromkeys(
                [
                    *(v.strip() for v in response.get("Vary", "").split(",") if v.strip()),
                    "Authorization",
                    "Cookie",
                ]
            )
        )

    @staticmethod
    def _conditional(request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add an ETag to a JSON answer, or answer 304 if the client has the same data.

        A successful `GET` with JSON gets a weak ETag (a hash of the body) and
        `Cache-Control: private, max-age=0, must-revalidate`. An error answer gets
        `Cache-Control: no-store`. Any other answer without a `Cache-Control` gets
        `private, no-store`.

        Args:
            request: The request. The method reads `If-None-Match`.
            response: The response to complete.

        Returns:
            The response, or an empty `304` response with the cache and rate-limit headers if
            the ETag matches.
        """
        is_json = response.get("Content-Type", "").startswith("application/json")
        if request.method != "GET" or response.status_code != 200 or not is_json:  # noqa: PLR2004
            if response.status_code >= 400:  # noqa: PLR2004
                response["Cache-Control"] = "no-store"
            elif "Cache-Control" not in response:
                response["Cache-Control"] = "private, no-store"
            return response
        etag = 'W/"' + hashlib.sha256(response.content).hexdigest()[:32] + '"'
        response["ETag"] = etag
        response["Cache-Control"] = "private, max-age=0, must-revalidate"
        wanted = [item.strip() for item in request.headers.get("If-None-Match", "").split(",")]
        if etag in wanted or "*" in wanted:
            not_modified = HttpResponse(status=304)
            for name in (
                "ETag",
                "Cache-Control",
                "Vary",
                "API-Version",
                "RateLimit-Limit",
                "RateLimit-Remaining",
                "RateLimit-Reset",
                "RateLimit-Policy",
            ):
                if name in response:
                    not_modified[name] = response[name]
            return not_modified
        return response
