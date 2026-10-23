"""Errors of the API in the `application/problem+json` format (RFC 9457).

Every error answer has the same fields:

- `type`: a link to the explanation of the error code in the developer docs.
- `title`: a short, fixed text for the status.
- `status`: the HTTP status.
- `detail`: a text for this case. It never holds a stack trace, a path, a setting or a secret.
- `instance`: the path of the request.
- `code`: a stable machine-readable code. Clients should branch on this value.
"""

import logging
from http import HTTPStatus

from django.http import Http404, HttpRequest, JsonResponse
from ninja import NinjaAPI
from ninja.errors import AuthenticationError, AuthorizationError, ValidationError

logger = logging.getLogger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"
DOCS_ERRORS_URL = "/docs/api/errors/"

#: The error codes of v1 and the HTTP status of each.
CODES: dict[str, int] = {
    "unauthenticated": 401,
    "invalid_token": 401,
    "token_expired": 401,
    "subscription_required": 403,
    "feature_not_available": 403,
    "email_verification_required": 403,
    "not_found": 404,
    "validation_error": 422,
    "rate_limited": 429,
    "server_error": 500,
    "api_disabled": 503,
    "email_delivery_failed": 503,
}


class ApiError(Exception):
    """An error that the API shows to the client as a problem document."""

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        headers: dict[str, str] | None = None,
        errors: list[dict] | None = None,
    ) -> None:
        """Save the code, the detail text, extra headers and field errors.

        Args:
            code: One of the keys of `CODES`. The status comes from it.
            detail: A text for this case. It must be safe to show to any client.
            headers: Extra response headers, for example `Retry-After`.
            errors: A list of field errors for a `validation_error`.
        """
        super().__init__(detail)
        self.code = code
        self.status = CODES[code]
        self.detail = detail
        self.headers = headers or {}
        self.errors = errors


def problem(
    request: HttpRequest,
    code: str,
    detail: str,
    *,
    headers: dict[str, str] | None = None,
    errors: list[dict] | None = None,
) -> JsonResponse:
    """Build the problem response for an error code.

    Args:
        request: The request. Its path is the `instance` of the problem.
        code: One of the keys of `CODES`.
        detail: A text for this case that is safe to show.
        headers: Extra response headers.
        errors: Field errors. They are added as the `errors` member.

    Returns:
        A `JsonResponse` with the status of the code and the problem content type.
    """
    status = CODES[code]
    body = {
        "type": f"{DOCS_ERRORS_URL}#{code}",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "instance": request.path,
        "code": code,
    }
    if errors:
        body["errors"] = errors
    response = JsonResponse(body, status=status, content_type=PROBLEM_CONTENT_TYPE)
    for name, value in (headers or {}).items():
        response[name] = value
    return response


def _clean_errors(raw: list[dict]) -> list[dict]:
    """Keep only the location, the message and the type of each field error.

    The raw errors of pydantic can hold the input value. The function drops it, so an answer
    never repeats what the client sent.

    Args:
        raw: The list of errors that ninja gives for a failed validation.

    Returns:
        One dict for each error with the keys `field`, `message` and `type`. The `field` is the
        path of the field, without the `query` or `path` part.
    """
    cleaned = []
    for item in raw:
        location = item.get("loc", ())
        cleaned.append(
            {
                "field": ".".join(str(part) for part in location if part not in {"query", "path"}),
                "message": str(item.get("msg", "")),
                "type": str(item.get("type", "")),
            }
        )
    return cleaned


def install(api: NinjaAPI) -> None:
    """Register the problem handlers on an API object.

    Args:
        api: The `NinjaAPI` of one version.
    """

    @api.exception_handler(ApiError)
    def _api_error(request: HttpRequest, exc: ApiError):
        """Answer an `ApiError` with its problem document."""
        return problem(request, exc.code, exc.detail, headers=exc.headers, errors=exc.errors)

    @api.exception_handler(ValidationError)
    def _validation(request: HttpRequest, exc: ValidationError):
        """Answer a bad parameter with a 422 problem. Field errors list what is wrong."""
        return problem(
            request,
            "validation_error",
            "One or more parameters are not valid.",
            errors=_clean_errors(exc.errors),
        )

    @api.exception_handler(AuthenticationError)
    def _unauthenticated(request: HttpRequest, exc: AuthenticationError):
        """Answer a request with no credentials."""
        return problem(
            request,
            "unauthenticated",
            "Send a Bearer token in the Authorization header, or sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @api.exception_handler(AuthorizationError)
    def _forbidden(request: HttpRequest, exc: AuthorizationError):
        """Answer a request that may not use the endpoint."""
        return problem(request, "feature_not_available", "You may not use this endpoint.")

    @api.exception_handler(Http404)
    def _not_found(request: HttpRequest, exc: Http404):
        """Answer a missing object."""
        return problem(request, "not_found", "The object does not exist.")

    @api.exception_handler(Exception)
    def _server_error(request: HttpRequest, exc: Exception):
        """Answer an unexpected error. The cause goes to the log, never to the client."""
        logger.error("Unhandled error in the API: %s %s", request.method, request.path)
        return problem(request, "server_error", "The server could not process the request.")
