"""Delivery preview access, history limits, and member/staff data visibility."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.access.models import FeatureBlock
from apps.delivery.models import DeliveryLog
from apps.reports.models import Report
from apps.siteconfig import conf
from apps.web.queries import latest_deliveries

pytestmark = pytest.mark.django_db
URL = "/api/app/delivery"


def test_session_feature_and_bearer_rules(client, member, make_token, auth):
    assert client.get(URL).status_code == 401
    assert client.get("/delivery/").status_code == 302
    client.force_login(member)
    _, secret = make_token(member)
    assert client.get(URL, headers=auth(secret)).status_code == 401
    FeatureBlock.objects.create(user=member, feature="delivery")
    response = client.get(URL)
    assert response.status_code == 403
    assert response.json()["code"] == "feature_not_available"
    assert client.get("/delivery/").status_code == 403


@pytest.mark.parametrize("is_staff", [False, True])
def test_subscription_staff_exemption_and_public_switch(client, member, expire, settings, is_staff):
    settings.SUBSCRIPTIONS_REQUIRED = True
    settings.API_ENABLED = False
    conf.invalidate()
    expire(member)
    member.is_staff = is_staff
    member.save(update_fields=["is_staff"])
    client.force_login(member)
    response = client.get(URL)
    assert response.status_code == (200 if is_staff else 403)
    assert client.get("/delivery/").status_code == (200 if is_staff else 302)
    if not is_staff:
        assert response.json()["code"] == "subscription_required"


@pytest.mark.parametrize("is_staff", [False, True])
def test_display_fields_and_diagnostics_visibility(client, member, settings, is_staff):
    settings.TELEGRAM_CHAT_IDS = [" 123456 ", "", "   ", "654321"]
    conf.invalidate()
    member.is_staff = is_staff
    member.save(update_fields=["is_staff"])
    report = Report.objects.create(date=date(2026, 10, 16), text="Report body not for this API")
    DeliveryLog.objects.create(report=report, channel="telegram", status="sent", recipient="123456")
    failed = DeliveryLog.objects.create(
        channel="email",
        status="failed",
        recipient="private@example.test",
        error="<b>Diagnostic</b> private@example.test",
    )
    before = list(DeliveryLog.objects.values())
    client.force_login(member)
    response = client.get(URL)
    body = response.json()
    assert body["chat_count"] == 2
    assert len(body["items"]) == 2
    first, second = body["items"]
    assert first["id"] == failed.pk
    assert first["channel"] == "Email"
    assert first["status"] == "failed"
    assert first["status_label"] == "Failed"
    assert first["report_date"] is None
    assert first["error"] == (failed.error if is_staff else None)
    assert first["created_at"] == failed.created_at.isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
    assert second["report_date"] == "2026-10-16"
    assert second["status_label"] == "Sent"
    for row in body["items"]:
        assert "recipient" not in row
        assert "report" not in row
    assert b"123456" not in response.content
    if not is_staff:
        assert b"private@example.test" not in response.content
    assert b"Report body" not in response.content
    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]
    assert list(DeliveryLog.objects.values()) == before


def test_newest_fifty_query_parity_and_deleted_reports(client, member):
    now = timezone.now()
    report = Report.objects.create(date=date(2026, 10, 16))
    rows = []
    for offset in range(52):
        row = DeliveryLog.objects.create(report=report, channel="telegram", status="sent")
        DeliveryLog.objects.filter(pk=row.pk).update(created_at=now - timedelta(minutes=offset))
        rows.append(row)
    report.delete()
    client.force_login(member)
    body = client.get(URL).json()
    assert len(body["items"]) == 50
    assert [row["id"] for row in body["items"]] == [row.pk for row in rows[:50]]
    assert [row["id"] for row in body["items"]] == [row.pk for row in latest_deliveries()]
    assert all(row["report_date"] is None for row in body["items"])


def test_delivery_stays_available_without_reports_feature(client, member):
    FeatureBlock.objects.create(user=member, feature="reports")
    client.force_login(member)
    assert client.get(URL).status_code == 200
    assert client.get("/delivery/").status_code == 200


def test_empty_preview_and_original_page(client, member, settings):
    settings.TELEGRAM_CHAT_IDS = []
    conf.invalidate()
    client.force_login(member)
    assert client.get(URL).json() == {"chat_count": 0, "items": []}
    preview = client.get("/delivery/")
    assert preview.status_code == 200
    assert b'id="root"' in preview.content
    assert "no-store" in preview["Cache-Control"]
    assert "web/delivery.html" not in [t.name for t in preview.templates]
