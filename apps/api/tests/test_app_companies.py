"""Company directory preview parity, private display fields, and access control."""

from datetime import UTC, datetime

import pytest

from apps.access.models import FeatureBlock
from apps.companies.models import Company
from apps.siteconfig import conf
from apps.web.queries import company_queryset

pytestmark = pytest.mark.django_db
URL = "/api/app/companies"


@pytest.fixture
def companies():
    return [
        Company.objects.create(name="Alpha Bank", symbol="ALPHA", sector="Finance"),
        Company.objects.create(name="Beta Tools", symbol="BETA", sector="Manufacturing"),
        Company.objects.create(name="Gamma Finance", symbol="GAMMA", sector="Services"),
    ]


def test_session_feature_and_token_rules(client, member, make_token, auth):
    assert client.get(URL).status_code == 401
    assert client.get("/app/companies/").status_code == 302
    client.force_login(member)
    _, secret = make_token(member)
    assert client.get(URL, headers=auth(secret)).status_code == 401
    FeatureBlock.objects.create(user=member, feature="companies")
    assert client.get(URL).json()["code"] == "feature_not_available"
    assert client.get(URL).status_code == 403
    assert client.get("/app/companies/").status_code == 403


@pytest.mark.parametrize("is_staff", [False, True])
def test_subscription_and_staff_exemption(client, member, expire, settings, is_staff):
    settings.SUBSCRIPTIONS_REQUIRED = True
    settings.API_ENABLED = False
    conf.invalidate()
    expire(member)
    member.is_staff = is_staff
    member.save(update_fields=["is_staff"])
    FeatureBlock.objects.create(user=member, feature="companies")
    client.force_login(member)
    response = client.get(URL)
    assert response.status_code == (200 if is_staff else 403)
    assert client.get("/app/companies/").status_code == (200 if is_staff else 302)
    if not is_staff:
        assert response.json()["code"] == "subscription_required"


@pytest.mark.parametrize("query", ["", "bank", "BETA", "finance", "unmatched"])
def test_query_and_ordering_parity(client, member, companies, query):
    client.force_login(member)
    body = client.get(URL, {"q": query}).json()
    assert [row["id"] for row in body["items"]] == list(
        company_queryset({"q": query}).values_list("pk", flat=True)
    )


def test_search_trimming_and_page_clamping(client, member, companies, settings):
    settings.WEB_PAGE_SIZE = 1
    conf.invalidate()
    client.force_login(member)
    body = client.get(URL).json()
    assert body["pages"] == body["total"] == 3
    assert body["items"][0]["name"] == "Alpha Bank"
    assert client.get(URL, {"page": 2}).json()["items"][0]["name"] == "Beta Tools"
    assert client.get(URL, {"page": 999}).json()["page"] == 3
    assert client.get(URL, {"page": -1}).json()["page"] == 1
    assert client.get(URL, {"q": " ALPHA "}).json()["total"] == 1
    empty = client.get(URL, {"q": "unmatched", "page": 99}).json()
    assert empty == {"items": [], "total": 0, "page": 1, "pages": 1}


@pytest.mark.parametrize("params", [{"q": "x" * 101}, {"page": "invalid"}, {"page": "1.5"}])
def test_invalid_filters_return_problem(client, member, params):
    client.force_login(member)
    response = client.get(URL, params)
    assert response.status_code == 422
    assert response["Content-Type"] == "application/problem+json"


def test_display_only_fields_and_read_only_behavior(client, member):
    company = Company.objects.create(
        name="<b>Plain company</b>",
        symbol="PLAIN",
        last_updated=datetime(2026, 10, 16, 23, tzinfo=UTC),
        screener_url="javascript:alert(1)",
        aliases=["Internal alias"],
        screener_data={"private": "scraped data"},
    )
    Company.objects.create(name="Unfetched", symbol="EMPTY")
    before = list(Company.objects.values())
    client.force_login(member)
    response = client.get(URL)
    body = response.json()
    row = body["items"][0]
    assert row == {
        "id": company.pk,
        "name": "<b>Plain company</b>",
        "symbol": "PLAIN",
        "sector": "",
        "screener_url": "javascript:alert(1)",
        "last_updated": "2026-10-16T23:00:00Z",
    }
    assert body["items"][1]["last_updated"] is None
    assert "aliases" not in row
    assert "screener_data" not in row
    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]
    assert list(Company.objects.values()) == before


def test_preview_and_legacy_remain_separate(client, member):
    client.force_login(member)
    preview = client.get("/app/companies/")
    assert preview.status_code == 200
    assert b'id="root"' in preview.content
    assert "no-store" in preview["Cache-Control"]
    legacy = client.get("/companies/")
    assert legacy.status_code == 200
    assert b'id="root"' not in legacy.content
    assert b"Search by name, symbol, or sector" in legacy.content
