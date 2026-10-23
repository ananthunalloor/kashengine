"""Telegram bot webhook used to verify account chat links."""

import hashlib
import hmac
import json
from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.access.rules import Access

from .models import DeliveryPreference, TelegramLink

MAX_WEBHOOK_BODY_BYTES = 64 * 1024
START_COMMAND_PARTS = 2


@login_not_required
@csrf_exempt
def telegram_webhook(request: HttpRequest) -> HttpResponse:
    """Consume only the configured Telegram webhook secret and one-time start payloads."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secret or not hmac.compare_digest(supplied, secret):
        return JsonResponse({"error": "unauthorized"}, status=401)
    if len(request.body) > MAX_WEBHOOK_BODY_BYTES:
        return JsonResponse({"error": "payload_too_large"}, status=413)
    try:
        update = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)
    if not isinstance(update, dict):
        return JsonResponse({"error": "invalid_json"}, status=400)
    return _handle_start_update(update)


def _handle_start_update(update: dict[str, Any]) -> JsonResponse:
    """Link an unexpired token from a Telegram private-chat /start update."""
    message = update.get("message") or {}
    if not isinstance(message, dict):
        return JsonResponse({"ok": True})
    text = message.get("text", "")
    chat = message.get("chat") or {}
    if not isinstance(text, str) or not isinstance(chat, dict):
        return JsonResponse({"ok": True})
    chat_id = chat.get("id")
    parts = text.split(maxsplit=1)
    if (
        len(parts) != START_COMMAND_PARTS
        or parts[0].split("@", 1)[0] != "/start"
        or chat_id is None
        or chat.get("type") != "private"
    ):
        return JsonResponse({"ok": True})
    token_hash = hashlib.sha256(parts[1].encode()).hexdigest()
    link = (
        TelegramLink.objects.filter(token_hash=token_hash, expires_at__gt=timezone.now())
        .select_related("user")
        .first()
    )
    if link is None:
        return JsonResponse({"ok": True})
    return _link_account(link, str(chat_id))


def _link_account(link: TelegramLink, chat_id: str) -> JsonResponse:
    """Check current account eligibility before consuming a Telegram link."""
    if not link.user.is_active or not Access(link.user).email_verified:
        return JsonResponse({"error": "email_verification_required"}, status=403)
    linked_elsewhere = DeliveryPreference.objects.filter(telegram_chat_id=str(chat_id)).exclude(
        user=link.user
    )
    if linked_elsewhere.exists():
        link.delete()
        return JsonResponse({"ok": True})
    preference, _ = DeliveryPreference.objects.get_or_create(user=link.user)
    preference.telegram_chat_id = str(chat_id)
    preference.telegram_reports = False
    preference.save(update_fields=["telegram_chat_id", "telegram_reports"])
    link.delete()
    return JsonResponse({"ok": True})
