"""Private Account preview and owner-scoped, CSRF-protected API token actions."""

import hashlib
import logging
import secrets
from datetime import timedelta
from typing import TYPE_CHECKING, cast

from django.conf import settings
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import floatformat
from django.utils import timezone
from ninja import Router, Status

from apps.access import features
from apps.access.middleware import access_for
from apps.api import tokens
from apps.api.errors import ApiError
from apps.api.models import ApiToken
from apps.api.v1.common import ERRORS, ERRORS_WITH_NOT_FOUND, ERRORS_WITH_VALIDATION
from apps.api.v1.schemas import Problem
from apps.delivery.models import DeliveryPreference, EmailVerification, TelegramLink
from apps.ops import audit
from apps.siteconfig import conf
from apps.web.queries import ACCOUNT_TOKEN_ROWS
from apps.web.signup import VerificationEmailError, send_verification_email

from .auth import AppSession
from .schemas import (
    Account,
    AccountDelivery,
    AccountToken,
    DeliveryChoices,
    TelegramLinkResponse,
    TokenCreate,
    TokenCreated,
)

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser

router = Router(tags=["Account"], auth=AppSession(allow_unverified=True))
logger = logging.getLogger(__name__)


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
    preference, _ = DeliveryPreference.objects.get_or_create(user=user)
    return {
        "username": user.get_username(),
        "email": getattr(user, "email", ""),
        "delivery": {
            "email_verified": preference.email_verified_at is not None,
            "email_reports": preference.email_reports,
            "telegram_connected": bool(preference.telegram_chat_id),
            "telegram_reports": preference.telegram_reports,
            "telegram_bot_username": settings.TELEGRAM_BOT_USERNAME,
        },
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
        "api_enabled": conf.API_ENABLED and access.email_verified,
        "api_docs": conf.API_ENABLED and conf.API_DOCS_ENABLED and access.email_verified,
        "tokens": [
            token_summary(token)
            for token in ApiToken.objects.filter(user=user)[:ACCOUNT_TOKEN_ROWS]
        ],
        "active_tokens": len(tokens.active_tokens(user, access.now)),
        "token_limit": conf.API_TOKEN_MAX_PER_USER,
        "token_days": conf.API_TOKEN_EXPIRY_DAYS,
    }


@router.post(
    "/account/delivery/email/verify",
    response={200: AccountDelivery, 503: Problem, **ERRORS_WITH_VALIDATION},
    operation_id="send_app_email_verification",
    summary="Send a new email verification link for the current account",
)
def resend_email_verification(request: HttpRequest):
    """Allow verification later, with a short cooldown and explicit delivery failures."""
    preference, _ = DeliveryPreference.objects.get_or_create(user=request.user)
    if preference.email_verified_at is not None:
        return _delivery_summary(preference)
    if not getattr(request.user, "email", ""):
        raise ApiError("validation_error", "Your account needs an email address. Contact an admin.")
    recent_expiry = timezone.now() + timedelta(hours=settings.EMAIL_VERIFICATION_HOURS, seconds=-60)
    if EmailVerification.objects.filter(user=request.user, expires_at__gt=recent_expiry).exists():
        raise ApiError(
            "validation_error", "Wait one minute before requesting another verification email."
        )
    try:
        send_verification_email(request.user, request)
    except VerificationEmailError as exc:
        logger.warning("Account verification email was not sent: %s", exc)
        raise ApiError(
            "email_delivery_failed", "We could not send the verification email. Try again later."
        ) from exc
    return _delivery_summary(preference)


@router.put(
    "/account/delivery",
    auth=AppSession(),
    response={200: AccountDelivery, **ERRORS_WITH_VALIDATION},
    operation_id="update_app_account_delivery",
    summary="Save the current user's report delivery channel choices",
)
def update_delivery(request: HttpRequest, payload: DeliveryChoices):
    """Save opted-in destinations only when the required verification is complete."""
    preference, _ = DeliveryPreference.objects.get_or_create(user=request.user)
    if payload.email_reports and preference.email_verified_at is None:
        raise ApiError("validation_error", "Verify your email before enabling email reports.")
    if payload.telegram_reports and not preference.telegram_chat_id:
        raise ApiError("validation_error", "Link your Telegram account before enabling reports.")
    preference.email_reports = payload.email_reports
    preference.telegram_reports = payload.telegram_reports
    preference.save(update_fields=["email_reports", "telegram_reports"])
    return _delivery_summary(preference)


@router.post(
    "/account/delivery/telegram/link",
    auth=AppSession(),
    response={200: TelegramLinkResponse, **ERRORS_WITH_VALIDATION},
    operation_id="create_app_telegram_link",
    summary="Create a short-lived Telegram bot link for the current user",
)
def create_telegram_link(request: HttpRequest):
    """Issue a one-time start link; the bot webhook validates its opaque token."""
    if not settings.TELEGRAM_BOT_USERNAME or not settings.TELEGRAM_WEBHOOK_SECRET:
        raise ApiError("validation_error", "Telegram account linking is not configured.")
    token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(minutes=15)
    TelegramLink.objects.update_or_create(
        user=request.user,
        defaults={
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "expires_at": expires_at,
        },
    )
    return {
        "url": f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}",
        "expires_at": expires_at,
    }


@router.post(
    "/account/delivery/telegram/unlink",
    auth=AppSession(),
    response={200: AccountDelivery, **ERRORS},
    operation_id="unlink_app_telegram",
    summary="Remove the current user's linked Telegram destination",
)
def unlink_telegram(request: HttpRequest):
    """Disconnect the chat and disable Telegram delivery for the current user."""
    preference, _ = DeliveryPreference.objects.get_or_create(user=request.user)
    preference.telegram_chat_id = None
    preference.telegram_reports = False
    preference.save(update_fields=["telegram_chat_id", "telegram_reports"])
    TelegramLink.objects.filter(user=request.user).delete()
    return _delivery_summary(preference)


def _delivery_summary(preference: DeliveryPreference) -> dict:
    """Return safe delivery preference fields without revealing the Telegram chat ID."""
    return {
        "email_verified": preference.email_verified_at is not None,
        "email_reports": preference.email_reports,
        "telegram_connected": bool(preference.telegram_chat_id),
        "telegram_reports": preference.telegram_reports,
        "telegram_bot_username": settings.TELEGRAM_BOT_USERNAME,
    }


@router.post(
    "/account/tokens",
    auth=AppSession(),
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
