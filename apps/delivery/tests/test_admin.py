"""Superuser-only manual verification through Django's user admin."""

from datetime import timedelta

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.utils import timezone

from apps.access.rules import Access
from apps.delivery.models import DeliveryPreference, EmailVerification
from apps.ops.models import AuditEvent

pytestmark = pytest.mark.django_db
USERS = "/admin/auth/user/"


def test_superuser_can_verify_an_existing_user_without_changing_other_settings(
    admin_client, admin_user, django_user_model
):
    user = django_user_model.objects.create_user(
        username="manual-verification", email="member@example.test", is_active=False
    )
    EmailVerification.objects.create(
        user=user, token_hash="a" * 64, expires_at=timezone.now() + timedelta(hours=1)
    )
    assert not Access(user).email_verified
    response = admin_client.post(
        USERS, {"action": "verify_email", "_selected_action": [user.pk]}, follow=True
    )
    assert response.status_code == 200
    preference = DeliveryPreference.objects.get(user=user)
    assert preference.email_verified_at is not None
    assert not preference.email_reports
    assert not preference.telegram_reports
    assert not EmailVerification.objects.filter(user=user).exists()
    user.refresh_from_db()
    assert not user.is_active
    assert Access(user).email_verified
    event = AuditEvent.objects.get(action="verify email")
    assert event.actor == admin_user
    assert event.target == user.username
    assert LogEntry.objects.filter(
        user=admin_user, object_id=str(user.pk), change_message__contains="email verified"
    ).exists()
    assert b"Marked 1 account email(s) verified" in response.content
    assert b"Email verified" in response.content
    accepted_at = preference.email_verified_at
    admin_client.post(USERS, {"action": "verify_email", "_selected_action": [user.pk]})
    preference.refresh_from_db()
    assert preference.email_verified_at == accepted_at
    assert AuditEvent.objects.filter(action="verify email").count() == 1


@pytest.mark.parametrize("email", ["", "not-an-email"])
def test_admin_rejects_missing_or_invalid_email(admin_client, django_user_model, email):
    user = django_user_model.objects.create_user(username="invalid-email", email=email)
    response = admin_client.post(
        USERS, {"action": "verify_email", "_selected_action": [user.pk]}, follow=True
    )
    assert b"add a valid email address before verification" in response.content
    assert not DeliveryPreference.objects.filter(
        user=user, email_verified_at__isnull=False
    ).exists()
    assert not AuditEvent.objects.filter(action="verify email").exists()


def test_non_superuser_cannot_use_manual_verification(client, django_user_model):
    staff = django_user_model.objects.create_user(username="staff-verifier", is_staff=True)
    staff.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="auth", codename__in=["view_user", "change_user"]
        )
    )
    user = django_user_model.objects.create_user(username="target", email="target@example.test")
    client.force_login(staff)
    response = client.get(USERS)
    assert response.status_code == 200
    assert b"Mark email verified" not in response.content
    client.post(USERS, {"action": "verify_email", "_selected_action": [user.pk]})
    assert not DeliveryPreference.objects.filter(
        user=user, email_verified_at__isnull=False
    ).exists()
    assert not AuditEvent.objects.filter(action="verify email").exists()
