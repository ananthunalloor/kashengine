"""Session-only authentication with CSRF and a separate UI request budget."""

from django.conf import settings
from django.http import HttpRequest
from ninja.security import APIKeyCookie

from apps.api import ratelimit
from apps.api.errors import ApiError


class AppSession(APIKeyCookie):
    """Accept active browser sessions, never bearer credentials; enforce CSRF on writes."""

    param_name = settings.SESSION_COOKIE_NAME

    def authenticate(self, request: HttpRequest, key: str | None):
        """Check the session without consuming the public API's rate budget.

        Args:
            request: The incoming request with the Django session.
            key: The session cookie read by Ninja; Django already resolved the user.

        Returns:
            The active user, or None if there is no authenticated session.

        Raises:
            ApiError: If authorization headers are supplied or the UI limit is exceeded.
        """
        if "Authorization" in request.headers:
            raise ApiError("unauthenticated", "Use a browser session, not an Authorization header.")
        user = request.user
        if not user.is_authenticated or not user.is_active:
            return None
        request.api_rate = ratelimit.hit(  # ty: ignore[unresolved-attribute]
            f"app:user:{user.pk}", limit=settings.APP_API_RATE_LIMIT_PER_MINUTE
        )
        return user
