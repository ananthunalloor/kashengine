"""Admin for the delivery log, sign-up invitations, legal records and email verification."""

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.ops import audit

from .models import (
    DeliveryLog,
    DeliveryPreference,
    EmailVerification,
    LegalAcceptance,
    SignupInvite,
)


class VerifiedUserAdmin(UserAdmin):
    """Add explicit, audited email verification to the existing Django user admin."""

    list_display = ("username", "email", "first_name", "last_name", "is_staff", "email_verified")
    actions = ("verify_email",)

    def get_queryset(self, request):
        """Load the delivery preference together with the users, so the list needs one query.

        Args:
            request: The admin request.

        Returns:
            The user query set with `select_related("delivery_preference")`.
        """
        return super().get_queryset(request).select_related("delivery_preference")

    @admin.display(boolean=True, description="Email verified")
    def email_verified(self, obj):
        """Show whether the email of the user is verified. Staff exemptions do not count here.

        Args:
            obj: The user.

        Returns:
            True if the user has a verified time. False if not, or if there is no preference.
        """
        try:
            return obj.delivery_preference.email_verified_at is not None
        except ObjectDoesNotExist:
            return False

    def has_verify_email_permission(self, request):
        """Allow the verify-email action for superusers only.

        Args:
            request: The admin request.

        Returns:
            True if the user is a superuser.
        """
        return request.user.is_superuser

    @admin.action(
        permissions=["verify_email"],
        description="Mark email verified (only after confirming email ownership)",
    )
    @transaction.atomic
    def verify_email(self, request, queryset):
        """Mark the email of the selected users as verified, after a superuser confirms ownership.

        The action skips a user who has no valid email address (and shows an error), and a user who
        is already verified. For each changed user it removes the pending verification link,
        writes an Ops audit event and adds an entry to the admin history.

        Args:
            request: The admin request. The user must be a superuser.
            queryset: The users that the admin selected.

        Raises:
            PermissionDenied: If the user is not a superuser.
        """
        if not request.user.is_superuser:
            raise PermissionDenied
        verified = 0
        for user in queryset:
            try:
                validate_email(user.email)
            except ValidationError:
                self.message_user(
                    request,
                    f"{user.get_username()}: add a valid email address before verification.",
                    level=messages.ERROR,
                )
                continue
            preference, _ = DeliveryPreference.objects.get_or_create(user=user)
            if preference.email_verified_at is not None:
                continue
            preference.email_verified_at = timezone.now()
            preference.save(update_fields=["email_verified_at"])
            EmailVerification.objects.filter(user=user).delete()
            audit.record(
                request.user,
                "verify email",
                user.get_username(),
                "Email ownership confirmed manually in Django admin.",
                request,
            )
            self.log_change(request, user, "Marked email verified after confirming ownership.")
            verified += 1
        self.message_user(
            request,
            f"Marked {verified} account email(s) verified. Existing verifications were unchanged.",
            level=messages.SUCCESS if verified else messages.INFO,
        )


admin.site.unregister(get_user_model())
admin.site.register(get_user_model(), VerifiedUserAdmin)


@admin.register(DeliveryLog)
class DeliveryLogAdmin(admin.ModelAdmin):
    """Admin for DeliveryLog."""

    list_display = ("created_at", "channel", "status", "recipient", "report")
    list_filter = ("channel", "status")
    search_fields = ("recipient", "error")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)


@admin.register(SignupInvite)
class SignupInviteAdmin(admin.ModelAdmin):
    """Generate a code on creation and reveal it only once to the administrator."""

    list_display = ("id", "created_at", "created_by", "used_at", "used_by", "revoked")
    list_filter = ("revoked",)
    readonly_fields = ("created_at", "created_by", "used_at", "used_by")
    fields = (*readonly_fields, "revoked")

    def save_model(self, request, obj, form, change):
        """Save an invitation. For a new one, make the code and show it one time in a message.

        Only the SHA-256 digest of the code is saved.

        Args:
            request: The admin request. Its user becomes the creator of a new invitation.
            obj: The invitation to save.
            form: The admin form.
            change: True when the invitation exists already. The code is then not changed.
        """
        if not change:
            code = obj.generate_code()
            obj.created_by = request.user
            self.message_user(
                request,
                f"Invite code (copy now; it will not be shown again): {code}",
            )
        super().save_model(request, obj, form, change)


@admin.register(LegalAcceptance)
class LegalAcceptanceAdmin(admin.ModelAdmin):
    """Expose immutable sign-up agreement records for administrators."""

    list_display = ("user", "version", "accepted_at")
    readonly_fields = ("user", "version", "accepted_at")

    def has_add_permission(self, request):
        """Return False. A record is created only during registration.

        Args:
            request: The admin request.

        Returns:
            Always False.
        """
        return False

    def has_change_permission(self, request, obj=None):
        """Return False. An accepted version and its time cannot be rewritten.

        Args:
            request: The admin request.
            obj: The record, or None for the list page.

        Returns:
            Always False.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """Return False. The record stays for the lifetime of the account.

        Args:
            request: The admin request.
            obj: The record, or None for the list page.

        Returns:
            Always False.
        """
        return False
