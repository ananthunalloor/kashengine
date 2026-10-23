"""Who is calling the API, and may the caller use the endpoint.

A call is accepted with one of two credentials:

1. A bearer token in the `Authorization` header: `Authorization: Bearer ke_<prefix>_<secret>`.
2. The session cookie of a signed-in web user. This is how the Swagger page works.

A bearer header that is present but wrong is always an error. It never falls back to the
session, so a client always learns that its token is bad.

After the caller is known, three checks run in this order:

1. The rate limit of the token or user (`apps.api.ratelimit`).
2. The subscription rule (only if "Require a subscription" is on).
3. The feature of the endpoint. The API uses the same rules as the web pages
   (`apps.access.rules.Access`), so an admin controls both in one place.
"""

from django.conf import settings
from django.http import HttpRequest
from ninja.security import APIKeyCookie, HttpBearer

from apps.access.rules import Access
from apps.ops.requestinfo import client_ip

from . import ratelimit, tokens
from .errors import ApiError
from .models import ApiToken

BEARER_CHALLENGE = 'Bearer realm="kash-engine-api"'


def gate(request: HttpRequest, user, identity: str, feature: str | None):
    """Run the rate limit and the access rules for a known caller.

    Args:
        request: The request. The user and the rate-limit window are saved on it.
        user: The user who owns the token or the session.
        identity: The rate-limit key, for example `token:12` or `user:7`.
        feature: The key of the feature that the endpoint belongs to, or None for an endpoint
            that every signed-in user may use.

    Returns:
        The user.

    Raises:
        ApiError: `rate_limited` (429), `subscription_required` (403) or
            `feature_not_available` (403).
    """
    request.api_rate = ratelimit.hit(identity)  # ty: ignore[unresolved-attribute]
    request.user = user
    access = Access(user)
    if not access.email_verified:
        raise ApiError(
            "email_verification_required",
            "Verify your email in Account settings to unlock all features.",
        )
    if feature is None:
        return user
    if not access.subscription_ok:
        raise ApiError(
            "subscription_required", "An active trial or subscription is needed to use the API."
        )
    if not access.can(feature):
        raise ApiError(
            "feature_not_available", f"Your account does not include the '{feature}' feature."
        )
    return user


def _authenticate_header(scheme: str, value: str) -> ApiToken:
    """Check the form of the `Authorization` header, then the token itself.

    Args:
        scheme: The first word of the header. It must be `Bearer` (any case).
        value: The rest of the header. It holds the token.

    Returns:
        The token row.

    Raises:
        tokens.TokenError: If the form is wrong or the token is not valid.
    """
    if scheme.lower() != "bearer" or not value.strip():
        raise tokens.TokenError("invalid_token", "Use the form: Authorization: Bearer <token>.")
    return tokens.authenticate(value)


def bearer_user(request: HttpRequest, feature: str | None):
    """Check the bearer token of a request. Return the user, or None if there is no header.

    Args:
        request: The request.
        feature: The feature of the endpoint, or None.

    Returns:
        The token owner, or None when the request has no `Authorization` header.

    Raises:
        ApiError: `invalid_token` or `token_expired` for a bad token, `rate_limited` when the
            client address has too many failed checks or the token is over its limit, and the
            gate errors of `gate`.
    """
    header = request.headers.get("Authorization", "")
    if not header.strip():
        return None
    address = client_ip(request) or "unknown"
    if ratelimit.is_blocked(address):
        raise ratelimit.block_response()
    scheme, _space, value = header.partition(" ")
    try:
        token = _authenticate_header(scheme, value)
    except tokens.TokenError as exc:
        ratelimit.record_failure(address)
        raise ApiError(
            exc.code, exc.message, headers={"WWW-Authenticate": BEARER_CHALLENGE}
        ) from None
    tokens.touch(token)
    request.api_token = token  # ty: ignore[unresolved-attribute]
    return gate(request, token.user, f"token:{token.pk}", feature)


def session_user(request: HttpRequest, feature: str | None):
    """Return the signed-in web user of a request, or None.

    Args:
        request: The request.
        feature: The feature of the endpoint, or None.

    Returns:
        The user when the session is valid and the user is active, else None.

    Raises:
        ApiError: The gate errors of `gate`.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_active:
        return None
    return gate(request, user, f"user:{user.pk}", feature)


def identify(request: HttpRequest, feature: str | None = None):
    """Return the caller of a request. Bearer first, then the session.

    Args:
        request: The request.
        feature: The feature of the endpoint, or None.

    Returns:
        The user, or None when the request has no credentials at all.

    Raises:
        ApiError: See `bearer_user` and `session_user`.
    """
    user = bearer_user(request, feature)
    return user if user is not None else session_user(request, feature)


class BearerToken(HttpBearer):
    """Bearer-token authentication. It also runs the rate limit and the access rules."""

    def __init__(self, feature: str | None = None) -> None:
        """Set the feature that the endpoints of this router belong to."""
        super().__init__()
        self.feature = feature

    def __call__(self, request: HttpRequest):
        """Return the user for a valid token, None if there is no header, or raise an error."""
        return bearer_user(request, self.feature)

    def authenticate(self, request: HttpRequest, token: str):
        """Return the user for the request. This is the method that ninja requires.

        `__call__` does the work and ninja normally does not reach this method. It calls the same
        function, so the result is the same.

        Args:
            request: The request.
            token: The token text that ninja read from the header. The method does not use it,
                because `bearer_user` reads the header again.

        Returns:
            The user, or None if the request has no `Authorization` header.

        Raises:
            ApiError: If the token is not valid, is expired, or a limit is passed.
        """
        return bearer_user(request, self.feature)


class SessionCookie(APIKeyCookie):
    """Session authentication for the Swagger page and for scripts that hold a session."""

    param_name = settings.SESSION_COOKIE_NAME

    def __init__(self, feature: str | None = None) -> None:
        """Set the feature that the endpoints of this router belong to."""
        super().__init__(csrf=False)
        self.feature = feature

    def authenticate(self, request: HttpRequest, key: str | None):
        """Return the signed-in user. The API has only GET endpoints, so CSRF does not apply.

        Args:
            request: The request.
            key: The session cookie value that ninja read. The method does not use it, because
                `session_user` reads the session of the request.

        Returns:
            The user of the session, or None if nobody is signed in.

        Raises:
            ApiError: If the user may not use the feature of this router, or a limit is passed.
        """
        return session_user(request, self.feature)


def for_feature(feature: str | None) -> list:
    """Return the auth list for a router: bearer token first, then the session.

    Args:
        feature: The feature key of the router, or None.

    Returns:
        A list for the `auth` argument of a ninja router.
    """
    return [BearerToken(feature), SessionCookie(feature)]
