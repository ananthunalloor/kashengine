"""Account preview ownership, subscription parity, CSRF, and one-time token privacy."""

import re
import smtplib
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.core import mail
from django.test import Client
from django.utils import timezone

from apps.access.models import FeatureBlock, Subscription
from apps.api import tokens
from apps.api.models import ApiToken
from apps.delivery.models import DeliveryPreference, EmailVerification, TelegramLink
from apps.ops.models import AuditEvent
from apps.siteconfig import conf
from apps.web import signup
from apps.web.views import _account_context

pytestmark = pytest.mark.django_db
URL = "/api/app/account"
CREATE = f"{URL}/tokens"
VERIFY = f"{URL}/delivery/email/verify"


def test_unverified_account_can_only_manage_verification_and_revoke_tokens(
    member, make_token, auth
):
    DeliveryPreference.objects.filter(user=member).update(email_verified_at=None)
    token, raw = make_token(member)
    client, headers = csrf_client(member)
    account = client.get(URL).json()
    assert not account["api_enabled"]
    assert not account["api_docs"]
    assert all(not feature["allowed"] for feature in account["features"])
    for endpoint in (CREATE, f"{URL}/delivery/telegram/link", f"{URL}/delivery/telegram/unlink"):
        response = client.post(
            endpoint, {"name": "blocked"}, content_type="application/json", headers=headers
        )
        assert response.status_code == 403
        assert response.json()["code"] == "email_verification_required"
    assert (
        Client().get("/api/v1/news", headers=auth(raw)).json()["code"]
        == "email_verification_required"
    )
    response = client.post(f"{CREATE}/{token.pk}/revoke", headers=headers)
    assert response.status_code == 200
    assert client.get(URL).status_code == 200


def test_resend_verification_is_owner_scoped_and_can_verify_later(client, member, settings):
    DeliveryPreference.objects.filter(user=member).update(email_verified_at=None)
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    client.force_login(member)
    response = client.post(VERIFY)
    assert response.status_code == 200
    assert not response.json()["email_verified"]
    assert mail.outbox[0].to == [member.email]
    previous = EmailVerification.objects.get(user=member).token_hash
    assert client.post(VERIFY).status_code == 422
    assert len(mail.outbox) == 1
    EmailVerification.objects.filter(user=member).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert client.post(VERIFY).status_code == 200
    assert EmailVerification.objects.get(user=member).token_hash != previous
    url = re.search(r"https?://\S+/verify-email/[^/\s]+/", mail.outbox[-1].body)
    assert url
    assert client.get(urlparse(url.group()).path).status_code == 200
    assert DeliveryPreference.objects.get(user=member).email_verified_at is not None
    assert client.post(VERIFY).json()["email_verified"]
    assert len(mail.outbox) == 2


def test_resend_verification_auth_and_csrf(client, member):
    assert client.post(VERIFY).status_code == 401
    protected, _headers = csrf_client(member)
    assert protected.post(VERIFY).status_code == 403
    assert not EmailVerification.objects.exists()


def test_resend_failure_preserves_existing_token_and_account(client, member, monkeypatch):
    DeliveryPreference.objects.filter(user=member).update(email_verified_at=None)
    client.force_login(member)
    existing = EmailVerification.objects.create(
        user=member, token_hash="a" * 64, expires_at=timezone.now() - timedelta(hours=1)
    )

    def failed_mail(*args, **kwargs):
        raise smtplib.SMTPException("SMTP unavailable")

    monkeypatch.setattr(signup, "send_mail", failed_mail)
    response = client.post(VERIFY)
    assert response.status_code == 503
    assert response.json()["code"] == "email_delivery_failed"
    existing.refresh_from_db()
    assert existing.token_hash == "a" * 64
    member.refresh_from_db()
    assert member.is_active


def test_resend_with_no_email_returns_explicit_error(client, member):
    DeliveryPreference.objects.filter(user=member).update(email_verified_at=None)
    member.email = ""
    member.save(update_fields=["email"])
    client.force_login(member)
    response = client.post(VERIFY)
    assert response.status_code == 422
    assert "needs an email" in response.json()["detail"]


def csrf_client(user):
    """Build a real session client with enforced CSRF and the session's CSRF cookie."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    client.get("/api/app/session")
    return client, {"X-CSRFToken": client.cookies["csrftoken"].value}


def test_auth_preview_cache_and_legacy_parity(client, member, make_token, auth):
    assert client.get(URL).status_code == 401
    assert client.get("/account/").status_code == 302
    client.force_login(member)
    _, secret = make_token(member)
    assert client.get(URL, headers=auth(secret)).status_code == 401
    response = client.get(URL)
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]
    body = response.json()
    context = _account_context(response.wsgi_request)
    assert body["username"] == member.get_username()
    assert body["email"] == member.email
    assert body["state"] == context["access"].state
    assert body["days_left"] == context["days_left"]
    assert body["required"] == context["required"]
    assert body["features"] == [
        {
            "key": row["feature"].key,
            "label": row["feature"].label,
            "help": row["feature"].help,
            "allowed": row["allowed"],
            "removed": row["removed"],
        }
        for row in context["rows"]
    ]
    preview = client.get("/account/")
    assert preview.status_code == 200
    assert b'id="root"' in preview.content
    assert "no-store" in preview["Cache-Control"]
    assert "web/account.html" not in [t.name for t in preview.templates]
    assert body["delivery"] == {
        "email_verified": True,
        "email_reports": False,
        "telegram_connected": False,
        "telegram_reports": False,
        "telegram_bot_username": "",
    }


@pytest.mark.parametrize("state", ["trial", "active", "expired", "none", "staff"])
def test_subscription_states_and_removed_features(client, member, settings, state):
    settings.SUBSCRIPTIONS_REQUIRED = True
    settings.SUBSCRIPTION_PRICE = 123.5
    settings.SUBSCRIPTION_CURRENCY = "INR"
    conf.invalidate()
    sub = Subscription.objects.get(user=member)
    if state == "none":
        sub.delete()
    else:
        sub.kind = "trial" if state == "trial" else "paid"
        sub.ends_at = timezone.now() - timedelta(days=1) if state == "expired" else None
        sub.save()
    if state == "staff":
        member.is_staff = True
        member.save(update_fields=["is_staff"])
    FeatureBlock.objects.create(user=member, feature="news")
    client.force_login(member)
    body = client.get(URL).json()
    assert body["state"] == state
    assert body["price"] == "123.50"
    assert body["currency"] == "INR"
    news = next(feature for feature in body["features"] if feature["key"] == "news")
    assert news["allowed"] == (state == "staff")
    assert news["removed"] == (state != "staff")
    assert client.get("/account/").status_code == 200


def test_token_metadata_excludes_secrets_hashes_and_other_users(client, member, staff):
    row, secret = tokens.issue(member, "<b>My token</b>")
    other, _ = tokens.issue(staff, "Other user's token")
    client.force_login(member)
    body = client.get(URL).json()
    assert len(body["tokens"]) == 1
    assert body["tokens"][0]["id"] == row.pk
    assert body["tokens"][0]["display"] == row.display
    assert set(body["tokens"][0]) == {
        "id",
        "name",
        "display",
        "created_at",
        "last_used_at",
        "expires_at",
        "state",
    }
    assert secret not in str(body)
    assert row.token_hash not in str(body)
    assert row.password_stamp not in str(body)
    assert other.display not in str(body)


def test_expired_token_metadata_does_not_count_as_active(client, member):
    row, _ = tokens.issue(member, "Expired")
    row.expires_at = timezone.now() - timedelta(seconds=1)
    row.save(update_fields=["expires_at"])
    client.force_login(member)
    body = client.get(URL).json()
    assert body["tokens"][0]["state"] == "expired"
    assert body["active_tokens"] == 0


def test_writes_reject_anonymous_and_authorization_even_with_csrf(member, auth):
    client, headers = csrf_client(member)
    anonymous = Client(enforce_csrf_checks=True)
    anonymous.cookies["csrftoken"] = headers["X-CSRFToken"]
    response = anonymous.post(
        CREATE, {"name": "Not allowed"}, content_type="application/json", headers=headers
    )
    assert response.status_code == 401
    assert "no-store" in response["Cache-Control"]
    assert not ApiToken.objects.exists()
    row, secret = tokens.issue(member, "Existing")
    headers.update(auth(secret))
    assert (
        client.post(
            CREATE, {"name": "Not allowed"}, content_type="application/json", headers=headers
        ).status_code
        == 401
    )
    assert client.post(f"{CREATE}/{row.pk}/revoke", headers=headers).status_code == 401
    row.refresh_from_db()
    assert row.revoked_at is None
    assert ApiToken.objects.count() == 1
    assert not AuditEvent.objects.filter(action__startswith="api token").exists()


def test_latest_twenty_and_full_active_count(client, member, settings):
    settings.API_TOKEN_MAX_PER_USER = 30
    conf.invalidate()
    older, _ = tokens.issue(member, "Old active")
    for index in range(21):
        token, _ = tokens.issue(member, f"Revoked {index}")
        tokens.revoke(token)
    client.force_login(member)
    body = client.get(URL).json()
    assert len(body["tokens"]) == 20
    assert older.pk not in [row["id"] for row in body["tokens"]]
    assert body["active_tokens"] == 1


def test_create_once_csrf_hash_audit_and_revoke(member):
    client, headers = csrf_client(member)
    assert (
        client.post(CREATE, {"name": "Excel"}, content_type="application/json").status_code == 403
    )
    assert not ApiToken.objects.exists()
    response = client.post(
        CREATE, {"name": " Excel "}, content_type="application/json", headers=headers
    )
    assert response.status_code == 201
    assert "no-store" in response["Cache-Control"]
    body = response.json()
    row = ApiToken.objects.get(user=member)
    secret = body["secret"]
    assert body["token"]["name"] == "Excel"
    assert row.token_hash == tokens.digest(secret)
    assert tokens.authenticate(secret).pk == row.pk
    event = AuditEvent.objects.get(action="api token create")
    assert event.actor == member
    assert event.detail == row.display
    assert secret not in str(list(AuditEvent.objects.values()))
    assert secret not in str(client.session.items())
    assert secret not in client.get(URL).content.decode()
    revoke = f"{CREATE}/{row.pk}/revoke"
    assert client.post(revoke).status_code == 403
    response = client.post(revoke, headers=headers)
    assert response.status_code == 200
    assert response.json()["state"] == "revoked"
    assert "no-store" in response["Cache-Control"]
    with pytest.raises(tokens.TokenError):
        tokens.authenticate(secret)
    assert client.post(revoke, headers=headers).status_code == 200
    assert AuditEvent.objects.filter(action="api token revoke").count() == 1


@pytest.mark.parametrize("payload", [{}, {"name": ""}, {"name": " "}, {"name": "x" * 61}])
def test_invalid_name_is_visible_and_never_creates(member, payload):
    client, headers = csrf_client(member)
    response = client.post(CREATE, payload, content_type="application/json", headers=headers)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert not ApiToken.objects.exists()


def test_limit_and_expiry_use_existing_service(member, settings):
    settings.API_TOKEN_MAX_PER_USER = 1
    settings.API_TOKEN_EXPIRY_DAYS = 2
    conf.invalidate()
    client, headers = csrf_client(member)
    response = client.post(
        CREATE, {"name": "First"}, content_type="application/json", headers=headers
    )
    assert response.status_code == 201
    row = ApiToken.objects.get()
    assert row.expires_at is not None
    assert timedelta(days=1, hours=23) < row.expires_at - timezone.now() <= timedelta(days=2)
    response = client.post(
        CREATE, {"name": "Second"}, content_type="application/json", headers=headers
    )
    assert response.status_code == 422
    assert "Revoke one" in response.json()["detail"]
    assert ApiToken.objects.count() == 1


def test_revoke_is_owner_scoped_and_requires_post(member, staff):
    row, _ = tokens.issue(staff, "Other")
    client, headers = csrf_client(member)
    assert client.post(f"{CREATE}/{row.pk}/revoke", headers=headers).status_code == 404
    row.refresh_from_db()
    assert row.revoked_at is None
    assert not AuditEvent.objects.filter(action="api token revoke").exists()
    assert client.get(f"{CREATE}/{row.pk}/revoke").status_code == 405
    assert client.get(CREATE).status_code == 405


def test_expired_account_can_manage_tokens_and_disabled_api_can_still_revoke(
    member, expire, settings
):
    settings.SUBSCRIPTIONS_REQUIRED = True
    conf.invalidate()
    expire(member)
    client, headers = csrf_client(member)
    response = client.post(
        CREATE, {"name": "Mine"}, content_type="application/json", headers=headers
    )
    assert response.status_code == 201
    row = ApiToken.objects.get()
    settings.API_ENABLED = False
    conf.invalidate()
    body = client.get(URL).json()
    assert not body["api_enabled"]
    assert not body["api_docs"]
    assert body["tokens"][0]["id"] == row.pk
    assert (
        client.post(
            CREATE, {"name": "No"}, content_type="application/json", headers=headers
        ).status_code
        == 503
    )
    assert client.post(f"{CREATE}/{row.pk}/revoke", headers=headers).status_code == 200
    assert client.get("/account/").status_code == 200


def test_account_delivery_requires_verified_destinations_and_links_telegram(member, settings):
    DeliveryPreference.objects.filter(user=member).update(email_verified_at=None)
    settings.TELEGRAM_BOT_USERNAME = "kash_test_bot"
    settings.TELEGRAM_WEBHOOK_SECRET = "webhook-secret-for-tests"
    client, headers = csrf_client(member)

    response = client.put(
        f"{URL}/delivery",
        {"email_reports": True, "telegram_reports": False},
        content_type="application/json",
        headers=headers,
    )
    assert response.status_code == 403
    assert "Verify your email" in response.json()["detail"]

    preference = DeliveryPreference.objects.get(user=member)
    preference.email_verified_at = timezone.now()
    preference.save(update_fields=["email_verified_at"])
    link_response = client.post(f"{URL}/delivery/telegram/link", headers=headers)
    assert link_response.status_code == 200
    link = link_response.json()
    token = parse_qs(urlparse(link["url"]).query)["start"][0]
    telegram_link = TelegramLink.objects.get(user=member)
    assert telegram_link.token_hash != token
    assert token not in telegram_link.token_hash

    DeliveryPreference.objects.filter(user=member).update(email_verified_at=None)
    blocked = client.post(
        "/api/telegram/webhook/",
        data=('{"message":{"text":"/start ' + token + '","chat":{"id":123456,"type":"private"}}}'),
        content_type="application/json",
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret-for-tests"},
    )
    assert blocked.status_code == 403
    assert (
        not DeliveryPreference.objects.filter(user=member).exclude(telegram_chat_id=None).exists()
    )
    preference.email_verified_at = timezone.now()
    preference.save(update_fields=["email_verified_at"])

    webhook_response = client.post(
        "/api/telegram/webhook/",
        data=('{"message":{"text":"/start ' + token + '","chat":{"id":123456,"type":"private"}}}'),
        content_type="application/json",
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret-for-tests"},
    )
    assert webhook_response.status_code == 200
    preference.refresh_from_db()
    assert preference.telegram_chat_id == "123456"
    assert not TelegramLink.objects.filter(user=member).exists()

    response = client.put(
        f"{URL}/delivery",
        {"email_reports": True, "telegram_reports": True},
        content_type="application/json",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["email_reports"]
    assert response.json()["telegram_reports"]
    assert "123456" not in client.get(URL).content.decode()

    response = client.post(f"{URL}/delivery/telegram/unlink", headers=headers)
    assert response.status_code == 200
    preference.refresh_from_db()
    assert preference.telegram_chat_id is None
    assert not preference.telegram_reports


def test_telegram_webhook_requires_secret_and_ignores_invalid_tokens(client, settings):
    settings.TELEGRAM_WEBHOOK_SECRET = "webhook-secret-for-tests"
    body = '{"message":{"text":"/start expired-or-unknown","chat":{"id":55}}}'
    assert (
        client.post(
            "/api/telegram/webhook/", data=body, content_type="application/json"
        ).status_code
        == 401
    )
    response = client.post(
        "/api/telegram/webhook/",
        data=body,
        content_type="application/json",
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret-for-tests"},
    )
    assert response.status_code == 200
    assert not DeliveryPreference.objects.filter(telegram_chat_id="55").exists()
