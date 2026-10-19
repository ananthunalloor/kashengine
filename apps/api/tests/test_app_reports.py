"""Reports preview contract, parity, and access checks."""

from datetime import date, timedelta

import pytest

from apps.access.models import FeatureBlock
from apps.delivery.models import DeliveryLog
from apps.markets.models import Prediction
from apps.reports.builder import gather, render_text
from apps.reports.models import Report
from apps.siteconfig import conf

pytestmark = pytest.mark.django_db
URL = "/api/app/reports"
DAY = date(2026, 10, 7)


@pytest.mark.parametrize("path", [URL, f"{URL}/{DAY}"])
def test_report_endpoints_require_browser_sessions(client, member, make_token, auth, path):
    assert client.get(path).status_code == 401
    client.force_login(member)
    _, token = make_token(member)
    assert client.get(path, headers=auth(token)).status_code == 401
    FeatureBlock.objects.create(user=member, feature="reports")
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["code"] == "feature_not_available"
    assert response["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("path", [URL, f"{URL}/{DAY}"])
def test_expired_subscription_is_denied(client, member, expire, settings, path):
    settings.SUBSCRIPTIONS_REQUIRED = True
    conf.invalidate()
    expire(member)
    client.force_login(member)
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["code"] == "subscription_required"


def test_report_pagination_and_empty_state(client, member, settings):
    settings.WEB_PAGE_SIZE = 2
    conf.invalidate()
    client.force_login(member)
    assert client.get(URL).json() == {
        "items": [],
        "page": 1,
        "pages": 1,
        "total": 0,
        "page_size": 2,
    }
    for offset in range(3):
        Report.objects.create(date=DAY + timedelta(days=offset), text="Report")

    first = client.get(URL).json()
    assert [item["date"] for item in first["items"]] == ["2026-10-09", "2026-10-08"]
    assert first["total"] == 3
    assert first["pages"] == 2
    assert "text" not in first["items"][0]
    assert client.get(URL, {"page": 2}).json()["items"][0]["date"] == DAY.isoformat()
    assert client.get(URL, {"page": 999}).json()["page"] == 2
    assert client.get(URL, {"page": -1}).json()["page"] == 1
    assert client.get(URL, {"page": "bad"}).status_code == 422


@pytest.mark.parametrize(
    ("confidence", "strength"), [(None, None), (0, "1.0/10"), (0.7, "7.3/10"), (1, "10.0/10")]
)
def test_report_strength_uses_the_existing_scale(client, member, confidence, strength):
    Report.objects.create(date=DAY, prediction="up", confidence=confidence)
    client.force_login(member)
    assert client.get(URL).json()["items"][0]["strength"] == strength


@pytest.mark.parametrize("is_staff", [False, True])
def test_report_details_preserve_display_and_hide_delivery_secrets(client, member, is_staff):
    member.is_staff = is_staff
    member.save(update_fields=["is_staff"])
    report = Report.objects.create(date=DAY, text="<script>Not HTML</script>\nSecond line")
    Report.objects.create(date=DAY - timedelta(days=2))
    Report.objects.create(date=DAY + timedelta(days=2))
    DeliveryLog.objects.create(
        report=report,
        channel="telegram",
        status="failed",
        recipient="private-recipient",
        error="Staff diagnostic",
    )
    client.force_login(member)
    response = client.get(f"{URL}/{DAY}")
    body = response.json()
    assert body["text"] == report.text
    assert body["older"] == "2026-10-05"
    assert body["newer"] == "2026-10-09"
    assert body["deliveries"][0]["channel"] == "Telegram"
    assert body["deliveries"][0]["status_label"] == "Failed"
    assert body["deliveries"][0]["error"] == ("Staff diagnostic" if is_staff else None)
    assert "private-recipient" not in response.text


def test_saved_data_is_reformatted_without_rewriting_the_original(client, member):
    prediction = Prediction.objects.create(
        target_date=DAY,
        direction="up",
        confidence=0.7,
        score=0.4,
    )
    data = gather(DAY, prediction)
    report = Report.objects.create(date=DAY, data=data, text="Original delivery text")
    client.force_login(member)
    response = client.get(f"{URL}/{DAY}")
    assert response.status_code == 200
    assert response.json()["text"] == render_text(data)
    assert response.json()["older"] is None
    assert response.json()["newer"] is None
    assert response.json()["deliveries"] == []
    report.refresh_from_db()
    assert report.text == "Original delivery text"
    assert report.data == data


def test_missing_and_invalid_dates_use_problem_responses(client, member):
    client.force_login(member)
    assert client.get(f"{URL}/{DAY}").json()["code"] == "not_found"
    assert client.get(f"{URL}/2026-02-30").status_code == 422


def test_staff_exemption_and_public_api_independence(client, staff, expire, settings):
    settings.API_ENABLED = False
    settings.SUBSCRIPTIONS_REQUIRED = True
    conf.invalidate()
    expire(staff)
    FeatureBlock.objects.create(user=staff, feature="reports")
    Report.objects.create(date=DAY, text="Still available")
    client.force_login(staff)
    assert client.get(URL).status_code == 200
    assert client.get(f"{URL}/{DAY}").status_code == 200
