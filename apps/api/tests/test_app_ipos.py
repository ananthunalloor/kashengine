"""IPO preview query parity, saved evidence, and feature/subscription access."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.access.models import FeatureBlock
from apps.ipos.models import Ipo
from apps.siteconfig import conf
from apps.web.queries import ipo_facts, ipo_queryset

pytestmark = pytest.mark.django_db
URL = "/api/app/ipos"


@pytest.fixture
def issues():
    return [
        Ipo.objects.create(
            name="Open Main",
            status="open",
            category="mainboard",
            verdict="good",
            open_date=date(2026, 10, 7),
        ),
        Ipo.objects.create(name="Upcoming SME", status="upcoming", category="sme", verdict=""),
        Ipo.objects.create(name="Closed Main", status="closed", verdict="mixed"),
        Ipo.objects.create(
            name="Listed SME",
            status="listed",
            category="sme",
            verdict="weak",
            listing_date=date(2026, 10, 1),
        ),
    ]


@pytest.mark.parametrize("detail", [False, True])
def test_session_and_feature_are_required(client, member, make_token, auth, issues, detail):
    path = f"{URL}/{issues[0].pk}" if detail else URL
    assert client.get(path).status_code == 401
    client.force_login(member)
    _, secret = make_token(member)
    assert client.get(path, headers=auth(secret)).status_code == 401
    FeatureBlock.objects.create(user=member, feature="ipos")
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["code"] == "feature_not_available"
    assert client.get(f"/app/ipos/{issues[0].pk}/" if detail else "/app/ipos/").status_code == 403


@pytest.mark.parametrize("is_staff", [False, True])
def test_subscription_and_staff_exemption(client, member, expire, settings, issues, is_staff):
    settings.SUBSCRIPTIONS_REQUIRED = True
    settings.API_ENABLED = False
    conf.invalidate()
    member.is_staff = is_staff
    member.save(update_fields=["is_staff"])
    expire(member)
    client.force_login(member)
    for path in (URL, f"{URL}/{issues[0].pk}"):
        response = client.get(path)
        assert response.status_code == (200 if is_staff else 403)
        if not is_staff:
            assert response.json()["code"] == "subscription_required"


@pytest.mark.parametrize(
    "filters",
    [
        {},
        {"status": "all"},
        {"status": "listed"},
        {"status": "open"},
        {"status": "upcoming"},
        {"status": "closed"},
        {"verdict": "unknown"},
        {"q": "Main", "category": "mainboard", "verdict": "good", "status": "all"},
        {"category": "sme"},
        {"verdict": "weak", "status": "all"},
    ],
)
def test_filter_and_ordering_parity(client, member, issues, filters):
    client.force_login(member)
    body = client.get(URL, filters).json()
    values = {"q": "", "status": "", "category": "", "verdict": "", **filters}
    assert [item["id"] for item in body["items"]] == list(
        ipo_queryset(values).values_list("pk", flat=True)
    )
    assert body["statuses"][0] == {"value": "", "label": "Active"}
    assert body["categories"] == [
        {"value": "mainboard", "label": "Mainboard"},
        {"value": "sme", "label": "SME"},
    ]


def test_pagination_and_search_trimming(client, member, issues, settings):
    settings.WEB_PAGE_SIZE = 1
    conf.invalidate()
    client.force_login(member)
    first = client.get(URL).json()
    assert first["total"] == first["pages"] == 3
    assert first["items"][0]["id"] == issues[0].pk
    assert client.get(URL, {"page": 2}).json()["page"] == 2
    assert client.get(URL, {"page": 999}).json()["page"] == 3
    assert client.get(URL, {"page": -1}).json()["page"] == 1
    assert client.get(URL, {"q": " Open "}).json()["total"] == 1


def test_detail_preserves_units_freshness_and_saved_scores(client, member):
    stamp = timezone.now() - timedelta(days=3)
    ipo = Ipo.objects.create(
        name="Example",
        status="listed",
        verdict="good",
        score=0.6,
        open_date=date(2026, 10, 7),
        close_date=date(2026, 10, 9),
        price_band_low=90,
        price_band_high=100,
        gmp=20,
        subscription_times=0,
        gmp_updated_at=stamp,
        subscription_updated_at=stamp,
        listing_gain_pct=-2.5,
        scored_at=stamp,
        source_url="https://example.test/ipo",
        score_inputs={
            "signals": [
                {"name": "gmp", "value": 20, "signal": 0.5},
                {"name": "subscription", "value": 0, "signal": -1},
                {"name": "news", "value": 0, "signal": 0},
            ],
            "notes": ["<b>Saved note</b>", "Stale metric."],
        },
    )
    original = ipo.score_inputs
    client.force_login(member)
    response = client.get(f"{URL}/{ipo.pk}")
    body = response.json()
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    assert body["score"] == "8.2/10"
    assert body["dates"] == "7 Oct to 9 Oct"
    assert body["gmp"] == "+20.0%"
    assert body["subscribed"] == "0.0x"
    assert body["listing_gain"] == "−2.5%"
    assert body["facts"] == [
        {"label": label, "value": value} for label, value in ipo_facts(ipo, timezone.now())
    ]
    assert "updated 3 days ago" in next(f["value"] for f in body["facts"] if f["label"] == "GMP")
    assert body["signals"] == [
        {"name": "GMP", "value": "+20.0%", "signal": "7.8/10"},
        {"name": "Subscription", "value": "0.0x", "signal": "1.0/10"},
        {"name": "News", "value": "5.5/10", "signal": "5.5/10"},
    ]
    assert body["notes"] == original["notes"]
    ipo.refresh_from_db()
    assert ipo.score_inputs == original
    assert ipo.scored_at == stamp


def test_unknown_and_missing_values_are_not_zero(client, member):
    ipo = Ipo.objects.create(name="Unknown")
    client.force_login(member)
    body = client.get(f"{URL}/{ipo.pk}").json()
    assert body["verdict"] == "unknown"
    assert body["score"] is None
    assert body["gmp"] == body["price_band"] == body["subscribed"] == "–"
    assert body["signals"] == body["notes"] == []
    assert body["scored_at"] is None
    assert body["source_url"] == ""


@pytest.mark.parametrize(
    "params",
    [
        {"q": "x" * 101},
        {"status": "bad"},
        {"category": "bad"},
        {"verdict": "bad"},
        {"page": "bad"},
    ],
)
def test_invalid_filters_are_problems(client, member, params):
    client.force_login(member)
    response = client.get(URL, params)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_preview_routes_and_original_pages(client, member):
    ipo = Ipo.objects.create(name="Compare me")
    assert client.get("/app/ipos/").status_code == 302
    assert client.get(f"/app/ipos/{ipo.pk}/").status_code == 302
    client.force_login(member)
    for path in ("/app/ipos/", f"/app/ipos/{ipo.pk}/"):
        response = client.get(path)
        assert response.status_code == 200
        assert 'id="root"' in response.text
        assert "no-store" in response["Cache-Control"]
    assert "web/ipos.html" in [t.name for t in client.get("/ipos/").templates]
    assert "web/ipo_detail.html" in [t.name for t in client.get(f"/ipos/{ipo.pk}/").templates]
    assert client.get(f"{URL}/999999").json()["code"] == "not_found"
    assert client.get(f"{URL}/invalid").status_code == 422
    assert client.get("/app/ipos/999999/").status_code == 404


def test_empty_list(client, member):
    client.force_login(member)
    body = client.get(URL).json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == body["pages"] == 1
