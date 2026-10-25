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
        """Return the email without outer spaces, if no account uses it.

        Raises:
            ValidationError: If an account has this email already (the check ignores case).
        """
        email = self.cleaned_data["email"].strip()
        if self.Meta.model.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_invite_code(self):
        """Return the invite code if it is valid. Open registration accepts any value.

        Raises:
            ValidationError: If the code is unknown, revoked, or already used.
        """
        code = self.cleaned_data["invite_code"]
        if not settings.SIGNUP_INVITE_REQUIRED:
            return code
        if not SignupInvite.objects.filter(
            token_hash=_token_digest(code), used_at__isnull=True, revoked=False
        ).exists():
            raise ValidationError("The invite code is invalid or has already been used.")
        return code

    def clean_legal_version(self):
        """Return the current agreement version if the form shows the same version.

        Raises:
            ValidationError: If the version differs. The user must reload the page.
        """
        if self.cleaned_data["legal_version"] != LEGAL_VERSION:
            raise ValidationError("The agreement has changed. Reload and review this page again.")
        return LEGAL_VERSION

    def save(self, commit=True):
        """Make the user with the email and an active account.

        Product features stay locked until the user verifies the email.

        Args:
            commit: If True, save the user. If False, return an unsaved user.

        Returns:
            The new user.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = True
        if commit:
            user.save()
            self.save_m2m()
        return user


def _token_digest(token: str) -> str:
    """Return the SHA-256 digest of a token as 64 hexadecimal characters.

    Args:
        token: The invite code or the verification token.

    Returns:
        The digest. The database keeps this value, never the token.
    """
    return hashlib.sha256(token.encode()).hexdigest()


class InviteUnavailableError(Exception):
    """The invite was redeemed or revoked after form validation."""


class VerificationEmailError(Exception):
    """The verification email could not be sent."""


@transaction.atomic
def send_verification_email(user, request: HttpRequest):
    """Make a new verification link and email it to the user.

    The previous link stops working when the new one is saved. If the email cannot be sent, the
    transaction is rolled back, so the previous link still works.

    Args:
        user: The user whose email must be verified.
        request: The request. The link uses its host name.

    Raises:
        VerificationEmailError: If the mail server fails or does not accept the message.
    """
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
    """Use the invitation, create the account, record the agreement and make the preferences.

    All steps run in one transaction. The account exists even if the verification email fails
    later.

    Args:
        form: The valid sign-up form.
        request: The request.

    Returns:
        The new user.

    Raises:
        InviteUnavailableError: If another request used or revoked the invitation after the form
            check.
    """
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
    """Show the sign-up page again with the typed values and the form errors.

    Args:
        request: The request.
        form: The sign-up form. The page never gets the password values.

    Returns:
        The response of the React sign-up page.
    """
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
    """Show the sign-up page, or create an account from the posted form.

    The account can sign in at once. The verification email goes out after the account exists. A
    failure to send it does not undo the account. A signed-in user goes to the dashboard.

    Args:
        request: The request. A `POST` has the sign-up fields.

    Returns:
        The sign-up page (with errors for a bad form), the confirmation page, or a redirect.
    """
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
    """Show the versioned Terms of Use and Privacy Notice to everyone.

    Args:
        request: The request.

    Returns:
        The legal page with the current `LEGAL_VERSION`.
    """
    return render(request, "web/legal.html", {"legal_version": LEGAL_VERSION})


@login_not_required
@never_cache
def verify_email(request: HttpRequest, token: str) -> HttpResponse:
    """Verify the email of the user that owns the link, then delete the link.

    The view does not turn on a disabled account. The link works one time.

    Args:
        request: The request.
        token: The token from the link. The database has only its digest.

    Returns:
        The confirmation page, or the same page with status `400` for an unknown or expired link.
    """
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
