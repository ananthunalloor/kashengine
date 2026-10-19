"""Private Account preview and owner-scoped, CSRF-protected API token actions."""

from typing import TYPE_CHECKING, cast

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import floatformat
from ninja import Router, Status

from apps.access import features
from apps.access.middleware import access_for
from apps.api import tokens
from apps.api.errors import ApiError
from apps.api.models import ApiToken
from apps.api.v1.common import ERRORS, ERRORS_WITH_NOT_FOUND, ERRORS_WITH_VALIDATION
from apps.api.v1.schemas import Problem
from apps.ops import audit
from apps.siteconfig import conf
from apps.web.queries import ACCOUNT_TOKEN_ROWS

from .auth import AppSession
from .schemas import Account, AccountToken, TokenCreate, TokenCreated

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser

router = Router(tags=["Account"], auth=AppSession())


def token_summary(token: ApiToken) -> AccountToken:
    """Serialize token metadata without exposing authentication material.

    Args:
        token: An owner-scoped token row.

    Returns:
        Safe metadata, including its masked display prefix and current state.
    """
    return AccountToken(
        id=token.pk,
        name=token.name,
        display=token.display,
        created_at=token.created_at,
        last_used_at=token.last_used_at,
        expires_at=token.expires_at,
        state=token.state,
    )


@router.get(
    "/account",
    response={200: Account, **ERRORS},
    operation_id="get_app_account",
    summary="Read the current user's subscription, feature access, and masked token metadata",
)
def get_account(request: HttpRequest):
    """Allow account access even after a subscription ends or the public API is disabled.

    Args:
        request: The authenticated browser request.

    Returns:
        Current account details with only owner-scoped token metadata.
    """
    access = access_for(request)
    sub = access.subscription
    user = cast("AbstractBaseUser", request.user)
    return {
        "username": user.get_username(),
        "email": getattr(user, "email", ""),
        "state": access.state,
        "subscription_kind": sub.kind if sub else None,
        "ends_at": sub.ends_at if sub else None,
        "days_left": sub.days_left(access.now) if sub else None,
        "subscription_ok": access.subscription_ok,
        "required": conf.SUBSCRIPTIONS_REQUIRED,
        "price": floatformat(conf.SUBSCRIPTION_PRICE, -2) if conf.SUBSCRIPTION_PRICE else "",
        "currency": conf.SUBSCRIPTION_CURRENCY,
        "period_days": conf.SUBSCRIPTION_PERIOD_DAYS,
        "contact": conf.SUBSCRIPTION_CONTACT_TEXT,
        "features": [
            {
                "key": feature.key,
                "label": feature.label,
                "help": feature.help,
                "allowed": access.can(feature.key),
                "removed": feature.key in access.blocked,
            }
            for feature in features.FEATURES
        ],
        "api_enabled": conf.API_ENABLED,
        "api_docs": conf.API_ENABLED and conf.API_DOCS_ENABLED,
        "tokens": [
            token_summary(token)
            for token in ApiToken.objects.filter(user=user)[:ACCOUNT_TOKEN_ROWS]
        ],
        "active_tokens": len(tokens.active_tokens(user, access.now)),
        "token_limit": conf.API_TOKEN_MAX_PER_USER,
        "token_days": conf.API_TOKEN_EXPIRY_DAYS,
    }


@router.post(
    "/account/tokens",
    response={201: TokenCreated, 503: Problem, **ERRORS_WITH_VALIDATION},
    operation_id="create_app_token",
    summary="Create a token and return its secret exactly once",
)
def create_token(request: HttpRequest, payload: TokenCreate):
    """Reuse issuance limits and audit only the masked prefix.

    Args:
        request: The authenticated, CSRF-checked browser request.
        payload: The token's display name.

    Returns:
        A 201 answer containing metadata and the one-time secret.

    Raises:
        ApiError: When the API is off, the name is empty, or the active-token limit is reached.
    """
    if not conf.API_ENABLED:
        raise ApiError(
            "api_disabled", "API access is disabled. You can still revoke existing tokens."
        )
    user = cast("AbstractBaseUser", request.user)
    try:
        row, secret = tokens.issue(user, payload.name)
    except ValueError as exc:
        raise ApiError("validation_error", str(exc)) from exc
    except tokens.TokenLimitError as exc:
        raise ApiError(
            "validation_error",
            f"You have {conf.API_TOKEN_MAX_PER_USER} active tokens. "
            "Revoke one before you make a new one.",
        ) from exc
    audit.record(user, "api token create", user.get_username(), row.display, request)
    return Status(201, {"token": token_summary(row), "secret": secret})


@router.post(
    "/account/tokens/{pk}/revoke",
    response={200: AccountToken, **ERRORS_WITH_NOT_FOUND},
    operation_id="revoke_app_token",
    summary="Revoke one token owned by the current user",
)
def revoke_token(request: HttpRequest, pk: int):
    """Permit revocation regardless of subscription or public API availability.

    Args:
        request: The authenticated, CSRF-checked browser request.
        pk: Token primary key; another owner's token is not found.

    Returns:
        Safe metadata for the revoked token; repeating the action does not audit twice.
    """
    token = get_object_or_404(ApiToken, pk=pk, user=request.user)
    if tokens.revoke(token):
        audit.record(
            request.user, "api token revoke", request.user.get_username(), token.display, request
        )
    return token_summary(token)
