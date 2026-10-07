"""Download the full text of articles.

Rules:
- Obey robots.txt. If robots.txt does not allow a URL, we do not fetch it.
- Wait between requests to the same host (NEWS_SCRAPE_DELAY_SECONDS, or the Crawl-delay
  in robots.txt if it is longer).
- Try each article once, unless the error is temporary (network error, HTTP 5xx or 429).
  A temporary error is tried again on the next run, until the article is too old.
"""

import logging
import re
import time
from datetime import timedelta
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura
from django.conf import settings
from django.utils import timezone

from .client import make_client
from .models import NewsArticle

logger = logging.getLogger(__name__)

# A page with less text than this is probably a paywall or an error page.
MIN_TEXT_CHARS = 200


class RobotsDisallowed(Exception):
    """robots.txt does not allow this URL."""


def robots_agent_name(user_agent: str) -> str:
    """Get the bot name that robots.txt rules match.

    "KashEngineBot/0.1" -> "KashEngineBot"
    "Mozilla/5.0 (compatible; KashEngineBot/0.1; +https://example.com)" -> "KashEngineBot"
    """
    match = re.search(r"compatible;\s*([A-Za-z0-9_-]+)", user_agent)
    name = match.group(1) if match else user_agent.split("/")[0].strip()
    return name or "*"


class PoliteFetcher:
    """Fetch URLs. Check robots.txt first and wait between requests to the same host."""

    def __init__(
        self,
        client: httpx.Client,
        delay: float,
        user_agent: str,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.client = client
        self.delay = delay
        self.agent = robots_agent_name(user_agent)
        self._sleep = sleep
        self._clock = clock
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request: dict[str, float] = {}

    def get(self, url: str) -> httpx.Response:
        """Fetch a URL. Raise RobotsDisallowed if robots.txt does not allow it."""
        parts = urlsplit(url)
        rules = self._rules(parts.scheme, parts.netloc)
        if not rules.can_fetch(self.agent, url):
            raise RobotsDisallowed(url)
        self._wait(parts.netloc, rules.crawl_delay(self.agent))
        return self.client.get(url)

    def _rules(self, scheme: str, host: str) -> RobotFileParser:
        key = f"{scheme}://{host}"
        if key not in self._robots:
            self._robots[key] = self._load_rules(key, host)
        return self._robots[key]

    def _load_rules(self, origin: str, host: str) -> RobotFileParser:
        rules = RobotFileParser()
        try:
            self._wait(host)
            response = self.client.get(f"{origin}/robots.txt")
        except httpx.HTTPError as exc:
            logger.warning("Cannot read robots.txt for %s: %s. Skip this host.", host, exc)
            rules.disallow_all = True
        else:
            if response.status_code >= 500:
                logger.warning(
                    "robots.txt for %s gave HTTP %s. Skip this host.", host, response.status_code
                )
                rules.disallow_all = True
            elif response.status_code >= 400:
                rules.allow_all = True  # No robots.txt file. Everything is allowed.
            else:
                rules.parse(response.text.splitlines())
        rules.modified()  # Without this, RobotFileParser refuses all URLs.
        return rules

    def _wait(self, host: str, crawl_delay: float | None = None) -> None:
        wait_for = max(self.delay, crawl_delay or 0)
        last = self._last_request.get(host)
        if last is not None:
            remaining = wait_for - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request[host] = self._clock()


def extract_text(html: str, url: str = "") -> str:
    """Get the main article text from a page. Return "" if there is not enough text."""
    text = trafilatura.extract(
        html,
        url=url or None,
        include_comments=False,
        include_tables=False,
    )
    text = (text or "").strip()
    return text if len(text) >= MIN_TEXT_CHARS else ""


def _scrape_one(article: NewsArticle, fetcher: PoliteFetcher) -> str:
    """Scrape one article. Return "scraped", "blocked", "failed", or "retry"."""
    try:
        response = fetcher.get(article.url)
    except RobotsDisallowed:
        _mark_tried(article)
        return "blocked"
    except httpx.HTTPError as exc:
        logger.warning("Network error for %s: %s", article.url, exc)
        return "retry"

    if response.status_code >= 500 or response.status_code == 429:
        logger.warning("HTTP %s for %s. Try again later.", response.status_code, article.url)
        return "retry"
    if response.status_code >= 400:
        logger.warning("HTTP %s for %s. Skip.", response.status_code, article.url)
        _mark_tried(article)
        return "failed"

    text = extract_text(response.text, article.url)
    if not text:
        logger.info("No article text found for %s", article.url)
        _mark_tried(article)
        return "failed"

    _mark_tried(article, text)
    return "scraped"


def _mark_tried(article: NewsArticle, text: str = "") -> None:
    article.text = text
    article.text_scraped_at = timezone.now()
    article.save(update_fields=["text", "text_scraped_at"])


def scrape_pending(
    client: httpx.Client | None = None,
    limit: int | None = None,
    sleep=time.sleep,
    clock=time.monotonic,
) -> dict:
    """Scrape full text for new articles. Return the number of articles for each result."""
    stats = {"scraped": 0, "blocked": 0, "failed": 0, "retry": 0}
    if not settings.NEWS_SCRAPE_FULL_TEXT:
        return {**stats, "disabled": True}

    cutoff = timezone.now() - timedelta(hours=settings.NEWS_SCRAPE_MAX_AGE_HOURS)
    pending = NewsArticle.objects.filter(
        text_scraped_at__isnull=True,
        text="",
        fetched_at__gte=cutoff,
    ).order_by("-fetched_at", "-id")[: limit or settings.NEWS_SCRAPE_BATCH_SIZE]

    own_client = client is None
    client = client or make_client()
    fetcher = PoliteFetcher(
        client,
        delay=settings.NEWS_SCRAPE_DELAY_SECONDS,
        user_agent=settings.NEWS_USER_AGENT,
        sleep=sleep,
        clock=clock,
    )
    try:
        for article in pending:
            stats[_scrape_one(article, fetcher)] += 1
    finally:
        if own_client:
            client.close()
    return stats
