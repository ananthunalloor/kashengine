"""Invite-gated sign-up and email confirmation."""

import hashlib
import logging
import secrets
import smtplib
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from apps.delivery.models import (
    DeliveryPreference,
    EmailVerification,
    LegalAcceptance,
    SignupInvite,
)

from .public_preview import preview_response

logger = logging.getLogger(__name__)
LEGAL_VERSION = "2026-10-23.3"


class SignupForm(UserCreationForm):
    """A new username and password with a valid email address and single-use invite."""

    email = forms.EmailField(max_length=254)
    invite_code = forms.CharField(max_length=100, strip=True)
    legal_version = forms.CharField(initial=LEGAL_VERSION, widget=forms.HiddenInput)
    agree_to_legal = forms.BooleanField(
        label="I agree to the Terms of Use and acknowledge the Privacy Notice.",
        error_messages={
            "required": "You must agree to the Terms of Use and acknowledge the Privacy Notice."
        },
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        """Make the invite field optional when the site allows open registration."""
        super().__init__(*args, **kwargs)
        self.fields["invite_code"].required = settings.SIGNUP_INVITE_REQUIRED

    def clean_email(self):
        """Require an email address not already in use."""
        email = self.cleaned_data["email"].strip()
        if self.Meta.model.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_invite_code(self):
        """Reject unknown, revoked, or previously redeemed invitations."""
        code = self.cleaned_data["invite_code"]
        if not settings.SIGNUP_INVITE_REQUIRED:
            return code
        if not SignupInvite.objects.filter(
            token_hash=_token_digest(code), used_at__isnull=True, revoked=False
        ).exists():
            raise ValidationError("The invite code is invalid or has already been used.")
        return code

    def clean_legal_version(self):
        """Require the agreement version displayed on the current sign-up page."""
        if self.cleaned_data["legal_version"] != LEGAL_VERSION:
            raise ValidationError("The agreement has changed. Reload and review this page again.")
        return LEGAL_VERSION

    def save(self, commit=True):
        """Allow login for verification while product features remain gated."""
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = True
        if commit:
            user.save()
            self.save_m2m()
        return user


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class InviteUnavailableError(Exception):
    """The invite was redeemed or revoked after form validation."""


class VerificationEmailError(Exception):
    """The verification email could not be sent."""


@transaction.atomic
def send_verification_email(user, request: HttpRequest):
    """Issue a fresh verification link, restoring the previous token if delivery fails."""
    token = secrets.token_urlsafe(32)
    expiry = timezone.now() + timedelta(hours=settings.EMAIL_VERIFICATION_HOURS)
    EmailVerification.objects.update_or_create(
        user=user, defaults={"token_hash": _token_digest(token), "expires_at": expiry}
    )
    verify_url = request.build_absolute_uri(reverse("web:verify_email", kwargs={"token": token}))
    try:
        sent = send_mail(
            "Verify your Kash Engine email",
            (
                "Your account is created. Verify your email to unlock all features:\n\n"
                f"{verify_url}\n\nThis link expires in "
                f"{settings.EMAIL_VERIFICATION_HOURS} hours."
            ),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except (OSError, smtplib.SMTPException) as exc:
        raise VerificationEmailError(str(exc)) from exc
    if not sent:
        raise VerificationEmailError("The email backend did not accept the message.")


@transaction.atomic
def _register(form: SignupForm, request: HttpRequest):
    """Redeem an invitation and create an account independently of email delivery."""
    invite = None
    if settings.SIGNUP_INVITE_REQUIRED:
        invite = SignupInvite.objects.filter(
            token_hash=_token_digest(form.cleaned_data["invite_code"]),
            used_at__isnull=True,
            revoked=False,
        )
        if not invite.update(used_at=timezone.now()):
            raise InviteUnavailableError
    user = form.save()
    if invite is not None:
        SignupInvite.objects.filter(
            token_hash=_token_digest(form.cleaned_data["invite_code"])
        ).update(used_by=user)
    LegalAcceptance.objects.create(user=user, version=form.cleaned_data["legal_version"])
    DeliveryPreference.objects.create(user=user)
    return user


def _signup_response(request: HttpRequest, form: SignupForm) -> HttpResponse:
    return preview_response(
        request,
        page="signup",
        invite_required=settings.SIGNUP_INVITE_REQUIRED,
        legal_version=LEGAL_VERSION,
        values={name: form[name].value() or "" for name in ("username", "email")},
        errors={name: list(errors) for name, errors in form.errors.items()},
    )


@login_not_required
@never_cache
def signup(request: HttpRequest) -> HttpResponse:
    """Create an account that can log in immediately and verify email later."""
    if request.user.is_authenticated:
        return redirect("web:dashboard")
    form = SignupForm(request.POST if request.method == "POST" else None)
    if request.method != "POST" or not form.is_valid():
        return _signup_response(request, form)
    try:
        user = _register(form, request)
    except InviteUnavailableError:
        form.add_error("invite_code", "The invite code is invalid or has already been used.")
        return _signup_response(request, form)
    email_sent = True
    try:
        send_verification_email(user, request)
    except VerificationEmailError as exc:
        email_sent = False
        logger.warning("Sign-up verification email was not sent: %s", exc)
    return preview_response(
        request,
        page="signup-complete",
        email=user.email,
        email_sent=email_sent,
        verification_hours=settings.EMAIL_VERIFICATION_HOURS,
    )


@login_not_required
def legal(request: HttpRequest) -> HttpResponse:
    """Publish the versioned terms and privacy notice referenced at sign-up."""
    return render(request, "web/legal.html", {"legal_version": LEGAL_VERSION})


@login_not_required
@never_cache
def verify_email(request: HttpRequest, token: str) -> HttpResponse:
    """Verify the email without changing an administrator's account activation decision."""
    verification = (
        EmailVerification.objects.select_related("user")
        .filter(token_hash=_token_digest(token), expires_at__gt=timezone.now())
        .first()
    )
    if verification is None:
        return render(request, "web/email_verification.html", {"valid": False}, status=400)
    user = verification.user
    preference, _ = DeliveryPreference.objects.get_or_create(user=user)
    preference.email_verified_at = timezone.now()
    preference.save(update_fields=["email_verified_at"])
    verification.delete()
    messages.success(request, "Your email is verified. You can now enable email reports.")
    return render(request, "web/email_verification.html", {"valid": True})
