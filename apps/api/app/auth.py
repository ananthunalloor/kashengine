"""Session-only authentication with CSRF and a separate UI request budget."""

from django.conf import settings
from django.http import HttpRequest
from ninja.security import APIKeyCookie

from apps.access.middleware import access_for
from apps.api import ratelimit
from apps.api.errors import ApiError


class AppSession(APIKeyCookie):
    """Accept active browser sessions, never bearer credentials; enforce CSRF on writes."""

    param_name = settings.SESSION_COOKIE_NAME

    def __init__(self, feature: str | None = None) -> None:
        """Optionally require a feature after authenticating the browser session."""
        super().__init__()
        self.feature = feature

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
        if self.feature is not None:
            access = access_for(request)
            if not access.subscription_ok:
                raise ApiError(
                    "subscription_required", "An active trial or subscription is needed."
                )
            if not access.can(self.feature):
                raise ApiError(
                    "feature_not_available",
                    f"Your account does not include the '{self.feature}' feature.",
                )
        return user


class OpsSession(AppSession):
    """Require the same staff flag as Django Ops, without subscription restrictions."""

    def authenticate(self, request: HttpRequest, key: str | None):
        """Reject non-staff sessions before any operational data is queried.

        Args:
            request: The browser request with the resolved Django user.
            key: The session cookie read by Ninja.

        Returns:
            The authenticated staff user, or None for an absent session.

        Raises:
            ApiError: If session authentication fails or the user is not staff.
        """
        user = super().authenticate(request, key)
        if user is not None and not user.is_staff:
            raise ApiError("feature_not_available", "Staff access is required for Ops.")
        return user
