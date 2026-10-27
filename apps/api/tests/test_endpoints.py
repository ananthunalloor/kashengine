import json

import pytest
from django.test import Client

from apps.api.v1.delivery import mask
from apps.markets.models import Prediction
from apps.news.models import NewsArticle
from apps.siteconfig import conf

pytestmark = pytest.mark.django_db


def test_health_needs_no_sign_in(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.0.0"}


def test_discovery_lists_the_versions(client):
    body = client.get("/api/").json()
    assert body["current"] == "v1"
    assert body["versions"][0]["version"] == "v1"
    assert body["versions"][0]["status"] == "stable"
    assert body["versions"][0]["openapi"] == "/api/v1/openapi.json"


def test_me(api, member):
    body = api("/api/v1/me").json()
    assert body["id"] == member.pk
    assert body["is_staff"] is False
    assert set(body["features"]) == {"reports", "news", "ipos", "markets", "companies", "delivery"}
    assert body["subscription"]["kind"] == "trial"
    assert body["subscription_required"] is False


def test_reports(api, data):
    page = api("/api/v1/reports").json()
    assert page["count"] == 1
    assert page["limit"] == 25
    assert page["offset"] == 0
    item = page["items"][0]
    assert item["date"] == "2026-10-07"
    assert item["prediction"] == "up"
    assert "text" not in item


def test_report_detail(api, data):
    body = api("/api/v1/reports/2026-10-07").json()
    assert body["text"] == "Report text"
    assert body["data"] == {"k": 1}


def test_report_not_found_is_a_problem(api, data):
    response = api("/api/v1/reports/2020-01-01")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response["Content-Type"].startswith("application/problem+json")


def test_report_with_a_bad_date_is_422(api, data):
    response = api("/api/v1/reports/not-a-date")
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_news_and_its_filters(api, data):
    page = api("/api/v1/news").json()
    assert page["count"] == 2
    scored = next(i for i in page["items"] if i["title"].startswith("Auto"))
    assert scored["sentiment"] == "positive"
    assert scored["companies"] == [{"symbol": "TATAMOTORS", "name": "Tata Motors"}]
    assert "text" not in scored
    assert api("/api/v1/news?sentiment=unscored").json()["count"] == 1
    assert api("/api/v1/news?sentiment=positive").json()["count"] == 1
    assert api("/api/v1/news?q=Auto").json()["count"] == 1
    assert api("/api/v1/news?source=Hindu").json()["count"] == 1
    assert api("/api/v1/news?since=2999-01-01T00:00:00Z").json()["count"] == 0


def test_news_rejects_a_bad_filter(api, data):
    response = api("/api/v1/news?sentiment=great")
    assert response.status_code == 422
    errors = response.json()["errors"]
    assert errors[0]["field"] == "sentiment"
    assert "input" not in json.dumps(errors)


def test_paging(api, data):
    first = api("/api/v1/news?limit=1").json()
    second = api("/api/v1/news?limit=1&offset=1").json()
    assert first["count"] == second["count"] == 2
    assert len(first["items"]) == len(second["items"]) == 1
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert api("/api/v1/news?limit=1&offset=5").json()["items"] == []


@pytest.mark.parametrize("query", ["limit=0", "limit=-1", "limit=abc", "offset=-1", "limit=501"])
def test_paging_rejects_bad_numbers(api, data, query):
    assert api(f"/api/v1/news?{query}").status_code == 422


def test_the_page_size_max_is_a_server_setting(api, data, settings):

    settings.API_PAGE_SIZE_MAX = 2
    conf.invalidate()
    assert api("/api/v1/news?limit=2").status_code == 200
    response = api("/api/v1/news?limit=3")
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "limit"


def test_ipos(api, data):
    page = api("/api/v1/ipos").json()
    assert page["count"] == 2
    acme = next(i for i in page["items"] if i["name"] == "Acme Ltd")
    assert acme["gmp"] == 20.0
    assert acme["gmp_pct"] == 20.0
    assert acme["verdict"] == "good"
    assert acme["company"]["symbol"] == "TATAMOTORS"
    assert api("/api/v1/ipos?status=active").json()["count"] == 1
    assert api("/api/v1/ipos?status=listed").json()["count"] == 1
    assert api("/api/v1/ipos?verdict=good").json()["count"] == 1
    assert api("/api/v1/ipos?category=sme").json()["count"] == 0
    assert api("/api/v1/ipos?q=acme").json()["count"] == 1


def test_ipo_detail(api, data):
    body = api(f"/api/v1/ipos/{data['ipo'].pk}").json()
    assert body["signals"] == [{"name": "gmp", "value": 20.0, "signal": 0.5, "strength": 1.0}]
    assert body["notes"] == ["No subscription number."]
    assert api("/api/v1/ipos/99999").status_code == 404


def test_ipo_unscored_verdict_is_null(api, data):
    old = next(i for i in api("/api/v1/ipos").json()["items"] if i["name"] == "Old Ltd")
    assert old["verdict"] is None
    assert old["score"] is None


def test_outlook(api, data):
    body = api("/api/v1/markets/outlook").json()
    assert body["direction"] == "up"
    assert body["strength"] == "strong"
    assert body["cues"][0]["symbol"] == "^GSPC"
    assert body["notes"] == ["One cue is missing."]
    assert body["correct"] is True


def test_outlook_before_the_first_prediction_is_404(api):
    assert api("/api/v1/markets/outlook").status_code == 404


def test_withheld_outlook_is_not_published_by_v1(api, data):
    Prediction.objects.update(direction="withheld", confidence=0, score=0, correct=None)
    assert api("/api/v1/markets/outlook").status_code == 404
    assert api("/api/v1/markets/predictions").json()["count"] == 0
    assert api("/api/v1/markets/accuracy").json()["total"] == 0


def test_predictions_accuracy_and_quotes(api, data):
    assert api("/api/v1/markets/predictions").json()["count"] == 1
    accuracy = api("/api/v1/markets/accuracy").json()
    assert accuracy["total"] == 1
    assert accuracy["accuracy"] == 1.0
    assert accuracy["enough_results"] is False
    quotes = api("/api/v1/markets/quotes").json()
    assert quotes[0]["close"] == 25000.5


def test_companies(api, data):
    page = api("/api/v1/companies?q=auto").json()
    assert page["count"] == 1
    assert page["items"][0]["aliases"] == ["Tata Motors Ltd"]
    assert "screener_data" not in page["items"][0]


def test_delivery_masks_the_recipient_and_hides_errors_from_users(api, data):
    item = api("/api/v1/delivery/logs").json()["items"][0]
    assert item["recipient"] == "…7890"
    assert item["error"] is None
    assert item["report_date"] == "2026-10-07"
    assert item["status"] == "failed"


def test_staff_see_the_delivery_error(staff_api, data):
    item = staff_api("/api/v1/delivery/logs").json()["items"][0]
    assert item["error"] == "Chat not found"
    assert item["recipient"] == "…7890"


def test_delivery_mask_function():

    assert mask("") == ""
    assert mask("12") == "…"
    assert mask("1234") == "…"
    assert mask("123456") == "…3456"


def test_only_get_is_allowed(api, data):

    assert Client().post("/api/v1/news").status_code in {401, 405}


def test_no_endpoint_returns_a_secret_or_internal_field(api, data):
    text = "".join(
        api(path).content.decode()
        for path in (
            "/api/v1/me",
            "/api/v1/news",
            "/api/v1/ipos",
            "/api/v1/companies",
            "/api/v1/delivery/logs",
            "/api/v1/markets/outlook",
        )
    )
    for forbidden in (
        "token_hash",
        "password",
        "screener_data",
        "sentiment_attempts",
        "text_scraped",
    ):
        assert forbidden not in text


def test_the_database_cost_of_a_news_page_does_not_grow(api, data, django_assert_max_num_queries):

    for i in range(20):
        NewsArticle.objects.create(source="S", title=f"t{i}", url=f"https://example.com/n{i}")
    with django_assert_max_num_queries(12):
        assert api("/api/v1/news?limit=25").status_code == 200
