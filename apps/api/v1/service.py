"""Service endpoints: health and the caller: `/api/v1/health`, `/api/v1/me`."""

from django.http import HttpRequest
from ninja import Router

from apps.access.rules import Access
from apps.siteconfig import conf

from ..auth import for_feature
from ..versions import VERSIONS
from .common import ERRORS
from .schemas import Health, Me

public = Router(tags=["Service"])
account = Router(tags=["Account"], auth=for_feature(None))


@public.get(
    "/health",
    auth=None,
    response=Health,
    operation_id="get_health",
    summary="Check that the API answers",
)
def get_health(request: HttpRequest):
    """Return `ok` and the version of the API contract. It needs no sign-in.

    Use it for a simple uptime check. It does not test the database.
    """
    return {"status": "ok", "version": VERSIONS["v1"].semver}


@account.get(
    "/me",
    response={200: Me, **ERRORS},
    operation_id="get_me",
    summary="Get the caller, the subscription and the features",
)
def get_me(request: HttpRequest):
    """Return who is calling, the subscription state and the features that the caller may use.

    Every signed-in user may call this endpoint, also a user whose subscription ended. It is the
    best first call to check that a token works.
    """
    user = request.user
    access = Access(user)
    subscription = access.subscription
    token = getattr(request, "api_token", None)
    return {
        "id": user.pk,
        "username": user.get_username(),
        "is_staff": bool(getattr(user, "is_staff", False)),
        "subscription_required": conf.SUBSCRIPTIONS_REQUIRED,
        "subscription": None
        if subscription is None
        else {
            "kind": subscription.kind,
            "state": access.state,
            "started_at": subscription.started_at,
            "ends_at": subscription.ends_at,
            "days_left": subscription.days_left(access.now),
        },
        "features": sorted(access.allowed),
        "token": token,
    }
