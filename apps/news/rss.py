"""Read RSS feeds and save new articles. Duplicates are removed by URL."""

import logging
from datetime import UTC, datetime
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import httpx
from django.utils.html import strip_tags

from .client import make_client
from .feeds import FEEDS, Feed
from .models import NewsArticle

logger = logging.getLogger(__name__)

URL_MAX_LENGTH = 1000
TITLE_MAX_LENGTH = 500
SUMMARY_MAX_LENGTH = 2000
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"}


def normalize_url(url: str) -> str:
    """Remove tracking parameters and the fragment, so the same article has one URL."""
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), "")
    )


def clean_text(value: str) -> str:
    """Remove HTML tags and extra spaces."""
    return " ".join(unescape(strip_tags(value or "")).split())


def _published_at(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def parse_feed(content: bytes) -> list[dict]:
    """Turn feed XML into a list of article data. Raise ValueError if it is not a feed."""
    data = feedparser.parse(content)
    # An HTML page, for example "Access denied", is not marked as bozo. It has no feed version.
    if not data.entries and (data.bozo or not data.version):
        reason = data.get("bozo_exception") or "the server did not send a feed (maybe a web page)"
        raise ValueError(f"Not a valid feed: {reason}")

    items = []
    for entry in data.entries:
        link = entry.get("link", "")
        title = clean_text(entry.get("title", ""))
        if not link or not title:
            continue
        url = normalize_url(link)
        if len(url) > URL_MAX_LENGTH:
            continue
        items.append(
            {
                "url": url,
                "title": title[:TITLE_MAX_LENGTH],
                "summary": clean_text(entry.get("summary", ""))[:SUMMARY_MAX_LENGTH],
                "published_at": _published_at(entry),
            }
        )
    return items


def save_articles(feed: Feed, items: list[dict]) -> int:
    """Save the articles that are not in the database yet. Return how many are new."""
    by_url = {item["url"]: item for item in items}  # Removes duplicates in the feed itself.
    existing = set(
        NewsArticle.objects.filter(url__in=by_url).values_list("url", flat=True),
    )
    new_articles = [
        NewsArticle(source=feed.source, **item)
        for url, item in by_url.items()
        if url not in existing
    ]
    # ignore_conflicts protects against two tasks that save the same URL at the same time.
    NewsArticle.objects.bulk_create(new_articles, ignore_conflicts=True)
    return len(new_articles)


def fetch_feed(feed: Feed, client: httpx.Client) -> int:
    """Download one feed and save its new articles. Return how many are new."""
    response = client.get(feed.url, headers={"Accept": "application/rss+xml, application/xml, */*"})
    response.raise_for_status()
    return save_articles(feed, parse_feed(response.content))


def fetch_all_feeds(feeds: list[Feed] | None = None, client: httpx.Client | None = None) -> dict:
    """Fetch all enabled feeds. One feed that fails does not stop the others.

    Return {"new": <total new articles>, "failed": {<feed label>: <error text>}}.
    """
    feeds = [f for f in (FEEDS if feeds is None else feeds) if f.enabled]
    own_client = client is None
    client = client or make_client()
    total_new = 0
    failed = {}
    try:
        for feed in feeds:
            label = f"{feed.source} - {feed.name}"
            try:
                new = fetch_feed(feed, client)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("Feed failed: %s: %s", label, exc)
                failed[label] = str(exc)
                continue
            logger.info("Feed ok: %s: %d new articles", label, new)
            total_new += new
    finally:
        if own_client:
            client.close()
    return {"new": total_new, "failed": failed}
