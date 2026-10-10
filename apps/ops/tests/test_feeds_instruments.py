"""The Ops pages for news feeds and market instruments."""

import httpx
import pytest
from django.urls import reverse

from apps.markets import instruments
from apps.markets.models import Instrument
from apps.news import rss
from apps.news.models import NewsArticle, NewsFeed
from apps.news.tests.test_rss import SAMPLE_FEED
from apps.ops.models import AuditEvent

pytestmark = pytest.mark.django_db

NEW_FEED = {"source": "Test News", "name": "Markets", "url": "https://news.test/rss"}


# Seeds


def test_the_first_migration_saves_the_feeds_and_instruments():
    assert NewsFeed.objects.filter(enabled=True).count() >= 5
    assert Instrument.objects.filter(kind=Instrument.Kind.TARGET).count() == 1
    assert instruments.global_cues()
    assert instruments.target_symbol()


# Access


@pytest.mark.parametrize("name", ["ops:feeds", "ops:instruments"])
def test_the_pages_follow_the_access_rules(
    client, member_client, staff_client, boss_client, offline, name
):
    url = reverse(name)

    assert client.get(url).status_code == 302
    assert member_client.get(url).status_code == 403
    assert staff_client.get(url).status_code == 200
    assert boss_client.get(url).status_code == 200


def test_a_staff_user_cannot_change_feeds_or_instruments(staff_client):
    feed, row = NewsFeed.objects.earliest("pk"), Instrument.objects.earliest("pk")
    posts = [
        (reverse("ops:feeds"), NEW_FEED),
        (reverse("ops:feed_toggle", args=[feed.pk]), {}),
        (reverse("ops:feed_delete", args=[feed.pk]), {}),
        (reverse("ops:instruments"), {}),
        (reverse("ops:instrument_save", args=[row.pk]), {}),
        (reverse("ops:instrument_delete", args=[row.pk]), {}),
    ]

    for url, data in posts:
        assert staff_client.post(url, data).status_code == 403

    assert not NewsFeed.objects.filter(url=NEW_FEED["url"]).exists()


# Feeds


def test_the_feed_page_shows_the_feeds_and_the_last_error(boss_client):
    feed = NewsFeed.objects.earliest("pk")
    feed.last_error = "HTTP 503 from the server"
    feed.save()

    page = boss_client.get(reverse("ops:feeds")).content.decode()

    assert feed.name in page
    assert "HTTP 503 from the server" in page


def test_a_superuser_adds_a_feed(boss_client):
    response = boss_client.post(reverse("ops:feeds"), NEW_FEED)

    assert response.status_code == 302
    assert NewsFeed.objects.filter(url=NEW_FEED["url"], enabled=True).exists()
    assert AuditEvent.objects.filter(action="add feed").exists()


@pytest.mark.parametrize("url", ["ftp://news.test/rss", "javascript:alert(1)"])
def test_a_feed_address_must_be_http_or_https(boss_client, url):
    response = boss_client.post(reverse("ops:feeds"), {**NEW_FEED, "url": url})

    assert response.status_code == 200
    assert not NewsFeed.objects.filter(source="Test News").exists()


def test_a_feed_address_without_a_scheme_becomes_https(boss_client):
    boss_client.post(reverse("ops:feeds"), {**NEW_FEED, "url": "news.test/plain"})

    assert NewsFeed.objects.filter(url="https://news.test/plain").exists()


def test_the_same_feed_address_is_refused_twice(boss_client):
    boss_client.post(reverse("ops:feeds"), NEW_FEED)

    response = boss_client.post(reverse("ops:feeds"), NEW_FEED)

    assert response.status_code == 200
    assert NewsFeed.objects.filter(url=NEW_FEED["url"]).count() == 1


def test_a_feed_is_turned_off_and_on(boss_client):
    feed = NewsFeed.objects.filter(enabled=True).earliest("pk")
    url = reverse("ops:feed_toggle", args=[feed.pk])

    boss_client.post(url)
    feed.refresh_from_db()
    assert feed.enabled is False
    assert feed.pk not in {f.pk for f in rss.load_feeds()}

    boss_client.post(url)
    feed.refresh_from_db()
    assert feed.enabled is True


def test_a_feed_is_deleted_and_its_articles_stay(boss_client):
    feed = NewsFeed.objects.earliest("pk")
    article = NewsArticle.objects.create(source=feed.source, title="t", url="https://news.test/x")
    response = boss_client.post(reverse("ops:feed_delete", args=[feed.pk]))

    assert response.status_code == 302
    assert not NewsFeed.objects.filter(pk=feed.pk).exists()
    assert AuditEvent.objects.filter(action="delete feed").exists()
    assert NewsArticle.objects.filter(pk=article.pk).exists()


def test_the_buttons_need_a_post(boss_client):
    feed, row = NewsFeed.objects.earliest("pk"), Instrument.objects.earliest("pk")

    assert boss_client.get(reverse("ops:feed_toggle", args=[feed.pk])).status_code == 405
    assert boss_client.get(reverse("ops:feed_delete", args=[feed.pk])).status_code == 405
    assert boss_client.get(reverse("ops:instrument_delete", args=[row.pk])).status_code == 405


def test_an_unknown_feed_is_a_404(boss_client):
    assert boss_client.post(reverse("ops:feed_toggle", args=[999999])).status_code == 404


def test_fetching_uses_the_feeds_of_the_database_and_saves_the_result(monkeypatch):
    NewsFeed.objects.all().delete()
    good = NewsFeed.objects.create(source="Test News", name="Good", url="https://news.test/good")
    bad = NewsFeed.objects.create(source="Test News", name="Bad", url="https://news.test/bad")
    NewsFeed.objects.create(
        source="Test News", name="Off", url="https://news.test/off", enabled=False
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/good":
            return httpx.Response(200, content=SAMPLE_FEED)
        if request.url.path == "/off":
            raise AssertionError("A disabled feed must not be requested.")
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = rss.fetch_all_feeds(client=client)

    good.refresh_from_db()
    bad.refresh_from_db()
    assert result["new"] == 2
    assert good.last_new_count == 2
    assert good.last_error == ""
    assert good.last_fetched_at is not None
    assert "503" in bad.last_error


# Instruments


def _symbol_post(**overrides):
    values = {
        "new-symbol": "^TEST",
        "new-name": "Test index",
        "new-kind": "cue",
        "new-weight": "0.2",
        "new-scale": "1.5",
        "new-enabled": "on",
    }
    values.update(overrides)
    return values


def _edit_post(row, **overrides):
    prefix = f"i{row.pk}"
    values = {
        f"{prefix}-symbol": row.symbol,
        f"{prefix}-name": row.name,
        f"{prefix}-kind": row.kind,
        f"{prefix}-weight": str(row.weight),
        f"{prefix}-scale": str(row.scale),
    }
    if row.enabled:
        values[f"{prefix}-enabled"] = "on"
    values.update({f"{prefix}-{key}": value for key, value in overrides.items()})
    return values


def _a_cue():
    return Instrument.objects.filter(kind=Instrument.Kind.CUE).earliest("pk")


def _the_target():
    return Instrument.objects.get(kind=Instrument.Kind.TARGET)


def test_the_page_shows_the_weight_total(boss_client):
    response = boss_client.get(reverse("ops:instruments"))

    total = instruments.total_cue_weight(instruments.global_cues())
    assert response.context["weight_total"] == pytest.approx(total)


def test_a_superuser_adds_an_instrument(boss_client):
    response = boss_client.post(reverse("ops:instruments"), _symbol_post())

    assert response.status_code == 302
    assert Instrument.objects.filter(symbol="^TEST", kind="cue", weight=0.2).exists()
    assert AuditEvent.objects.filter(action="add instrument").exists()
    assert "^TEST" in {c.symbol for c in instruments.global_cues()}


def test_a_second_target_is_refused(boss_client):
    response = boss_client.post(reverse("ops:instruments"), _symbol_post(**{"new-kind": "target"}))

    assert response.status_code == 200
    assert Instrument.objects.filter(kind="target").count() == 1


@pytest.mark.parametrize(("field", "value"), [("weight", "1.5"), ("weight", "-2"), ("scale", "0")])
def test_a_weight_or_scale_out_of_range_is_refused(boss_client, field, value):
    response = boss_client.post(reverse("ops:instruments"), _symbol_post(**{f"new-{field}": value}))

    assert response.status_code == 200
    assert not Instrument.objects.filter(symbol="^TEST").exists()


def test_a_superuser_changes_a_weight(boss_client):
    row = _a_cue()

    response = boss_client.post(
        reverse("ops:instrument_save", args=[row.pk]), _edit_post(row, weight="0.33")
    )

    row.refresh_from_db()
    assert response.status_code == 302
    assert row.weight == pytest.approx(0.33)
    assert AuditEvent.objects.filter(action="change instrument").exists()


def test_a_bad_weight_is_not_saved_and_the_page_says_why(boss_client):
    row = _a_cue()
    before = row.weight

    response = boss_client.post(
        reverse("ops:instrument_save", args=[row.pk]), _edit_post(row, weight="7"), follow=True
    )

    row.refresh_from_db()
    assert row.weight == before
    assert "Not saved" in response.content.decode()


def test_a_cue_can_be_turned_off(boss_client):
    row = _a_cue()
    data = _edit_post(row)
    data.pop(f"i{row.pk}-enabled", None)

    boss_client.post(reverse("ops:instrument_save", args=[row.pk]), data)

    assert row.symbol not in {c.symbol for c in instruments.global_cues()}


def test_the_target_cannot_be_turned_off_or_changed_to_another_kind(boss_client):
    target = _the_target()
    url = reverse("ops:instrument_save", args=[target.pk])
    off = _edit_post(target)
    off.pop(f"i{target.pk}-enabled")

    boss_client.post(url, off)
    boss_client.post(url, _edit_post(target, kind="cue"))

    target.refresh_from_db()
    assert target.enabled is True
    assert target.kind == "target"


def test_the_target_cannot_be_deleted(boss_client):
    target = _the_target()

    boss_client.post(reverse("ops:instrument_delete", args=[target.pk]))

    assert Instrument.objects.filter(pk=target.pk).exists()


def test_a_cue_is_deleted(boss_client):
    row = _a_cue()

    boss_client.post(reverse("ops:instrument_delete", args=[row.pk]))

    assert not Instrument.objects.filter(pk=row.pk).exists()
    assert AuditEvent.objects.filter(action="delete instrument").exists()


def test_without_a_target_the_prediction_cannot_start():
    Instrument.objects.filter(kind="target").delete()

    with pytest.raises(instruments.NoTargetError):
        instruments.target_symbol()
