"""Tests for the RSS reader. They do not use the network."""

from datetime import UTC, datetime

import httpx
import pytest

from apps.news.feeds import Feed
from apps.news.models import NewsArticle
from apps.news.rss import fetch_all_feeds, normalize_url, parse_feed, save_articles

SAMPLE_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Markets</title>
    <item>
      <title>Sensex jumps 500 points</title>
      <link>https://news.test/a?utm_source=rss&amp;id=1</link>
      <description>&lt;p&gt;Banks &amp;amp; IT lead the rally.&lt;/p&gt;</description>
      <pubDate>Sun, 04 Oct 2026 08:47:37 +0530</pubDate>
    </item>
    <item>
      <title>Sensex jumps 500 points (updated)</title>
      <link>https://news.test/a?id=1&amp;utm_medium=feed#top</link>
      <description>Same article, new tracking parameters.</description>
    </item>
    <item>
      <title>An item with no link</title>
      <description>This item is skipped.</description>
    </item>
    <item>
      <title>Rupee ends flat</title>
      <link>https://news.test/b</link>
    </item>
  </channel>
</rss>
"""


def test_normalize_url_removes_tracking_and_fragment():
    url = "HTTPS://News.Test/a?utm_source=rss&id=1&fbclid=x#top"
    assert normalize_url(url) == "https://news.test/a?id=1"


def test_parse_feed_reads_fields_and_skips_bad_items():
    items = parse_feed(SAMPLE_FEED)

    assert [item["url"] for item in items] == [
        "https://news.test/a?id=1",
        "https://news.test/a?id=1",
        "https://news.test/b",
    ]
    first = items[0]
    assert first["title"] == "Sensex jumps 500 points"
    assert first["summary"] == "Banks & IT lead the rally."
    # 08:47:37 +05:30 is 03:17:37 UTC.
    assert first["published_at"] == datetime(2026, 10, 4, 3, 17, 37, tzinfo=UTC)
    assert items[2]["published_at"] is None


def test_parse_feed_rejects_a_page_that_is_not_a_feed():
    with pytest.raises(ValueError, match=r"Not a valid feed"):
        parse_feed(b"<html><body>Access denied</body></html>")


@pytest.mark.django_db
def test_save_articles_removes_duplicates():
    feed = Feed("Test News", "Markets", "https://news.test/rss")
    items = parse_feed(SAMPLE_FEED)

    assert save_articles(feed, items) == 2  # The duplicate inside the feed is dropped.
    assert save_articles(feed, items) == 0  # A second run adds nothing.
    assert NewsArticle.objects.count() == 2
    assert set(NewsArticle.objects.values_list("source", flat=True)) == {"Test News"}


@pytest.mark.django_db
def test_fetch_all_feeds_continues_when_one_feed_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/good":
            return httpx.Response(200, content=SAMPLE_FEED)
        if request.url.path == "/off":
            raise AssertionError("A disabled feed must not be requested.")
        return httpx.Response(503)

    feeds = [
        Feed("Test News", "Broken", "https://news.test/broken"),
        Feed("Test News", "Good", "https://news.test/good"),
        Feed("Test News", "Off", "https://news.test/off", enabled=False),
    ]
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_all_feeds(feeds, client)

    assert result["new"] == 2
    assert list(result["failed"]) == ["Test News - Broken"]
