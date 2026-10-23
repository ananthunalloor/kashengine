"""Admin for the delivery log."""

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
        """Load verification state with the users rather than once per row."""
        return super().get_queryset(request).select_related("delivery_preference")

    @admin.display(boolean=True, description="Email verified")
    def email_verified(self, obj):
        """Show actual email verification, independently of staff feature exemptions."""
        try:
            return obj.delivery_preference.email_verified_at is not None
        except ObjectDoesNotExist:
            return False

    def has_verify_email_permission(self, request):
        """Only superusers may attest to email ownership."""
        return request.user.is_superuser

    @admin.action(
        permissions=["verify_email"],
        description="Mark email verified (only after confirming email ownership)",
    )
    @transaction.atomic
    def verify_email(self, request, queryset):
        """Verify valid emails, invalidate pending links, and audit each changed account."""
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
        """Keep only the code digest; never reset the redemption record."""
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
        """Acceptances are created only during registration."""
        return False

    def has_change_permission(self, request, obj=None):
        """Do not allow accepted versions or timestamps to be rewritten."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Keep the agreement record for the lifetime of the account."""
        return False
