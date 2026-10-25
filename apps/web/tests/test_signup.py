"""Invite-gated registration and one-time email verification."""

import hashlib
import re
import smtplib
from urllib.parse import urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core import mail
from django.test import Client, RequestFactory

from apps.delivery.models import (
    DeliveryPreference,
    EmailVerification,
    LegalAcceptance,
    SignupInvite,
)
from apps.web import signup

pytestmark = pytest.mark.django_db

SIGNUP_DATA = {
    "username": "new-member",
    "email": "new-member@example.test",
    "invite_code": "private-invite",
    "agree_to_legal": "on",
    "legal_version": signup.LEGAL_VERSION,
    "password1": "Market-Strong-Password-983!",
    "password2": "Market-Strong-Password-983!",
}


@pytest.fixture(autouse=True)
def signup_settings(settings):
    settings.SIGNUP_INVITE_REQUIRED = True
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    return SignupInvite.objects.create(
        token_hash=hashlib.sha256(SIGNUP_DATA["invite_code"].encode()).hexdigest()
    )


def test_signup_allows_login_before_verification_but_gates_email_reports(settings):
    settings.SIGNUP_INVITE_REQUIRED = True
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    client = Client()

    response = client.post("/signup/", SIGNUP_DATA)

    assert response.status_code == 200
    assert response.context["preview"]["page"] == "signup-complete"
    assert response.context["preview"]["email_sent"]
    user = get_user_model().objects.get(username="new-member")
    assert user.is_active
    login = client.post(
        "/login/", {"username": SIGNUP_DATA["username"], "password": SIGNUP_DATA["password1"]}
    )
    assert login.status_code == 302
    assert client.get("/api/app/account").status_code == 200
    assert client.get("/dashboard/")["Location"] == "/account/"
    assert client.get("/news/")["Location"] == "/account/"
    session = client.get("/api/app/session").json()
    assert session["features"] == []
    assert not session["email_verified"]
    assert [item["url"] for item in session["navigation"]] == ["/account/"]
    assert "Verify your email" in session["notice"]
    for endpoint in (
        "/api/app/today",
        "/api/app/news",
        "/api/app/reports",
        "/api/app/ipos",
        "/api/app/markets",
        "/api/app/companies",
        "/api/app/delivery",
        "/api/app/calendar?year=2026",
        "/api/app/events",
        "/api/v1/news",
        "/api/v1/docs",
    ):
        denied = client.get(endpoint)
        assert denied.status_code == 403, (endpoint, denied.content)
        assert denied.json()["code"] == "email_verification_required"
    delivery = client.put(
        "/api/app/account/delivery",
        {"email_reports": True, "telegram_reports": False},
        content_type="application/json",
    )
    assert delivery.status_code == 403
    assert delivery.json()["code"] == "email_verification_required"
    preference = DeliveryPreference.objects.get(user=user)
    assert preference.email_verified_at is None
    invite = SignupInvite.objects.get(used_by=user)
    assert invite.used_at is not None
    acceptance = LegalAcceptance.objects.get(user=user)
    assert acceptance.version == signup.LEGAL_VERSION
    assert acceptance.accepted_at is not None
    verification = EmailVerification.objects.get(user=user)
    verify_url = re.search(r"https?://\S+/verify-email/([^/\s]+)/", str(mail.outbox[0].body))
    assert verify_url is not None
    token = verify_url.group(1)
    assert token not in verification.token_hash
    assert client.get(urlsplit(verify_url.group(0)).path).status_code == 200

    user.refresh_from_db()
    preference.refresh_from_db()
    assert user.is_active
    assert preference.email_verified_at is not None
    assert client.get("/dashboard/").status_code == 200
    assert client.get("/api/app/today").status_code == 200
    assert client.get("/api/app/session").json()["features"]
    assert not EmailVerification.objects.filter(user=user).exists()
    assert (
        client.put(
            "/api/app/account/delivery",
            {"email_reports": True, "telegram_reports": False},
            content_type="application/json",
        ).status_code
        == 200
    )
    assert client.get(urlsplit(verify_url.group(0)).path).status_code == 400


@pytest.mark.parametrize(
    "changes",
    [
        {"invite_code": "wrong"},
        {"email": "not-an-email"},
        {"password2": "does-not-match"},
        {"agree_to_legal": ""},
        {"legal_version": "old-version"},
    ],
)
def test_signup_rejects_invalid_invite_email_and_password(settings, changes):
    settings.SIGNUP_INVITE_REQUIRED = True
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    response = Client().post("/signup/", {**SIGNUP_DATA, **changes})
    assert response.status_code == 200
    assert not get_user_model().objects.filter(username="new-member").exists()
    assert not mail.outbox
    assert SignupInvite.objects.get().used_at is None


def test_signup_can_be_opened_by_disabling_invite_requirement(settings):
    settings.SIGNUP_INVITE_REQUIRED = False
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    response = Client().post("/signup/", {**SIGNUP_DATA, "invite_code": ""})
    assert response.status_code == 200
    assert get_user_model().objects.get(username="new-member").is_active
    assert len(mail.outbox) == 1


def test_existing_email_cannot_be_used_for_another_account(settings, django_user_model):
    settings.SIGNUP_INVITE_REQUIRED = False
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    django_user_model.objects.create_user(
        username="already-registered",
        email=SIGNUP_DATA["email"],
        password="Existing-Password-983!",
    )
    response = Client().post("/signup/", {**SIGNUP_DATA, "invite_code": ""})
    assert response.status_code == 200
    assert not get_user_model().objects.filter(username="new-member").exists()


def test_invite_cannot_register_a_second_account():
    client = Client()
    client.post("/signup/", SIGNUP_DATA)
    response = client.post(
        "/signup/",
        {**SIGNUP_DATA, "username": "second-member", "email": "second@example.test"},
    )
    assert b"invalid or has already been used" in response.content
    assert not get_user_model().objects.filter(username="second-member").exists()
    assert len(mail.outbox) == 1


def test_revoked_invite_cannot_be_redeemed(signup_settings):
    signup_settings.revoked = True
    signup_settings.save(update_fields=["revoked"])
    response = Client().post("/signup/", SIGNUP_DATA)
    assert b"invalid or has already been used" in response.content
    assert not get_user_model().objects.filter(username="new-member").exists()


def test_stale_validated_form_cannot_reuse_invite():
    first = signup.SignupForm(SIGNUP_DATA)
    second = signup.SignupForm(
        {**SIGNUP_DATA, "username": "second-member", "email": "second@example.test"}
    )
    assert first.is_valid()
    assert second.is_valid()
    request = RequestFactory().get("/signup/")
    signup._register(first, request)
    with pytest.raises(signup.InviteUnavailableError):
        signup._register(second, request)
    assert not get_user_model().objects.filter(username="second-member").exists()
    assert LegalAcceptance.objects.count() == 1
    assert len(mail.outbox) == 0


@pytest.mark.parametrize("raises", [False, True])
def test_email_failure_keeps_account_agreement_and_consumes_invite(
    monkeypatch, signup_settings, raises
):
    def failed_mail(*args, **kwargs):
        if raises:
            raise smtplib.SMTPException("SMTP unavailable")
        return 0

    monkeypatch.setattr(signup, "send_mail", failed_mail)
    response = Client().post("/signup/", SIGNUP_DATA)
    assert response.context["preview"]["page"] == "signup-complete"
    assert not response.context["preview"]["email_sent"]
    user = get_user_model().objects.get(username="new-member")
    assert user.is_active
    assert LegalAcceptance.objects.filter(user=user).exists()
    assert not EmailVerification.objects.exists()
    signup_settings.refresh_from_db()
    assert signup_settings.used_at is not None
    assert signup_settings.used_by == user


def test_legal_page_and_unchecked_signup_agreement_are_public():
    client = Client()
    response = client.get("/legal/")
    assert response.status_code == 200
    assert b"Terms of Use" in response.content
    assert b"Privacy Notice" in response.content
    assert b"not investment advice" in response.content
    response = client.get("/signup/")
    assert b'id="root"' in response.content
    assert response.context["preview"]["page"] == "signup"
    assert response.context["preview"]["legal_version"] == signup.LEGAL_VERSION
    assert response.context["preview"]["values"] == {"username": "", "email": ""}
    assert "private" in response["Cache-Control"]
    assert "no-store" in response["Cache-Control"]


def test_open_registration_still_requires_legal_agreement(settings):
    settings.SIGNUP_INVITE_REQUIRED = False
    response = Client().post("/signup/", {**SIGNUP_DATA, "agree_to_legal": ""})
    assert b"You must agree" in response.content
    assert not get_user_model().objects.filter(username="new-member").exists()


def test_signup_react_validation_retains_only_username_and_email():
    response = Client().post("/signup/", {**SIGNUP_DATA, "password2": "wrong-password"})
    preview = response.context["preview"]
    assert preview["page"] == "signup"
    assert preview["values"] == {
        "username": SIGNUP_DATA["username"],
        "email": SIGNUP_DATA["email"],
    }
    assert "password2" in preview["errors"]
    assert SIGNUP_DATA["password1"] not in response.content.decode()
    assert "wrong-password" not in response.content.decode()
    assert SIGNUP_DATA["invite_code"] not in response.content.decode()
    assert "web/signup.html" not in [template.name for template in response.templates]


def test_signup_post_requires_csrf():
    response = Client(enforce_csrf_checks=True).post("/signup/", SIGNUP_DATA)
    assert response.status_code == 403
    assert not get_user_model().objects.filter(username="new-member").exists()
    assert SignupInvite.objects.get().used_at is None


def test_verification_does_not_reactivate_disabled_account():
    client = Client()
    client.post("/signup/", SIGNUP_DATA)
    user = get_user_model().objects.get(username="new-member")
    get_user_model().objects.filter(pk=user.pk).update(is_active=False)
    verify_url = re.search(r"https?://\S+/verify-email/([^/\s]+)/", str(mail.outbox[0].body))
    assert verify_url
    assert client.get(urlsplit(verify_url.group(0)).path).status_code == 200
    user.refresh_from_db()
    assert not user.is_active


def test_admin_generates_single_use_code_and_only_stores_digest(admin_client, admin_user):
    response = admin_client.post(
        "/admin/delivery/signupinvite/add/", {"_save": "Save"}, follow=True
    )
    assert response.status_code == 200
    messages = [str(message) for message in get_messages(response.wsgi_request)]
    code_message = next(message for message in messages if "Invite code (copy now;" in message)
    code = code_message.rsplit(": ", 1)[1]
    invite = SignupInvite.objects.get(created_by=admin_user)
    assert invite.token_hash == hashlib.sha256(code.encode()).hexdigest()
    assert code != invite.token_hash
    assert invite.used_at is None
    response = admin_client.get(f"/admin/delivery/signupinvite/{invite.pk}/change/")
    assert response.status_code == 200
    assert code.encode() not in response.content
    response = Client().post("/signup/", {**SIGNUP_DATA, "invite_code": code})
    assert response.context["preview"]["page"] == "signup-complete"
    invite.refresh_from_db()
    assert invite.used_at is not None
    assert invite.used_by.username == SIGNUP_DATA["username"]


def test_non_admin_cannot_generate_invites(client, django_user_model):
    user = django_user_model.objects.create_user(username="ordinary-member")
    client.force_login(user)
    response = client.post("/admin/delivery/signupinvite/add/", {"_save": "Save"})
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]
    assert SignupInvite.objects.count() == 1
