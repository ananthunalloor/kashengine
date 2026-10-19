"""Private application endpoints. These do not belong to the public versioned contract."""

from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.urls import reverse
from ninja import NinjaAPI
from ninja.errors import AuthenticationError, HttpError

from apps.access.middleware import access_for
from apps.api import errors
from apps.api.v1.common import ERRORS
from apps.siteconfig import conf
from apps.web.context import navigation_for

from .account import router as account_router
from .auth import AppSession
from .companies import router as companies_router
from .delivery import router as delivery_router
from .ipos import router as ipos_router
from .markets import router as markets_router
from .news import router as news_router
from .reports import router as reports_router
from .schemas import Session
from .today import router as today_router

api = NinjaAPI(
    title="Kash Engine App API",
    version="0.1.0",
    urls_namespace="api-app",
    auth=AppSession(),
    docs_url=None,
    openapi_url=None,
)
errors.install(api)
api.add_router("", reports_router)
api.add_router("", news_router)
api.add_router("", ipos_router)
api.add_router("", markets_router)
api.add_router("", companies_router)
api.add_router("", delivery_router)
api.add_router("", today_router)
api.add_router("", account_router)


@api.exception_handler(AuthenticationError)
def session_required(request: HttpRequest, exc: AuthenticationError):
    """Answer expired sessions without a login redirect or bearer challenge.

    Args:
        request: The request that failed authentication.
        exc: The authentication failure.

    Returns:
        A 401 problem response instructing the browser to sign in.
    """
    return errors.problem(request, "unauthenticated", "Sign in to continue.")


@api.exception_handler(HttpError)
def http_error(request: HttpRequest, exc: HttpError):
    """Render Ninja's CSRF rejection in the private API's problem format.

    Args:
        request: The rejected request.
        exc: Ninja's HTTP failure, including CSRF failures from cookie authentication.

    Returns:
        A problem response for CSRF errors, or Ninja's standard HTTP response otherwise.
    """
    if exc.status_code == 403 and str(exc) == "CSRF check Failed":  # noqa: PLR2004
        return JsonResponse(
            {
                "type": "about:blank",
                "title": "Forbidden",
                "status": 403,
                "code": "csrf_failed",
                "detail": "CSRF verification failed. Reload the page and try again.",
                "instance": request.path,
            },
            status=403,
            content_type=errors.PROBLEM_CONTENT_TYPE,
        )
    return api.create_response(request, {"detail": str(exc)}, status=exc.status_code)


@api.get(
    "/session",
    response={200: Session, **ERRORS},
    operation_id="get_app_session",
    summary="Get the current browser session and visible navigation",
    tags=["Session"],
)
def get_session(request: HttpRequest):
    """Return the signed-in user's permissions, even when their subscription has ended.

    Args:
        request: The authenticated browser request.

    Returns:
        Session details and feature-filtered links using the same rules as Django templates.
    """
    get_token(request)
    user = request.user
    access = access_for(request)
    return {
        "id": user.pk,
        "username": user.get_username(),
        "is_staff": bool(getattr(user, "is_staff", False)),
        "is_superuser": bool(getattr(user, "is_superuser", False)),
        "features": sorted(access.allowed),
        "subscription_required": conf.SUBSCRIPTIONS_REQUIRED,
        "subscription_ok": access.subscription_ok,
        "subscription_state": access.state,
        "notice": access.notice(),
        "navigation": navigation_for(request),
        "logout_url": reverse("web:logout"),
    }
