"""Tests for the article scraper. They do not use the network."""

from datetime import timedelta

import httpx
import pytest
from django.utils import timezone

from apps.news.models import NewsArticle
from apps.news.scraper import MIN_TEXT_CHARS, extract_text, robots_agent_name, scrape_pending

# The paragraphs must be different. The text extractor removes repeated paragraphs.
ARTICLE_HTML = """<html><head><title>Sensex jumps</title></head><body>
<nav><a href="/">Home</a> <a href="/markets">Markets</a></nav>
<article><h1>Sensex jumps 500 points</h1>
<p>The benchmark Sensex rose sharply on Friday as banks and IT stocks led the rally, while
foreign investors bought shares worth several hundred crore rupees.</p>
<p>Analysts said the rupee was stable against the dollar, and bond yields eased after the
latest inflation data came in below the forecast of most economists.</p>
<p>Traders now wait for the central bank policy meeting next week, which may give a clear
signal about the path of interest rates for the rest of the year.</p>
</article><footer>Copyright</footer></body></html>"""


class Site:
    """A fake website. It records every request path."""

    def __init__(self, robots: tuple[int, str] = (404, ""), pages: dict | None = None):
        self.robots = robots
        self.pages = pages if pages is not None else {}
        self.requested: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requested.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(self.robots[0], text=self.robots[1])
        status, body = self.pages.get(request.url.path, (404, ""))
        return httpx.Response(status, text=body)


def run(site: Site, **kwargs) -> tuple[dict, list[float]]:
    """Run the scraper against a fake site. Return the stats and the waits."""
    sleeps: list[float] = []
    with httpx.Client(transport=httpx.MockTransport(site)) as client:
        stats = scrape_pending(client, sleep=sleeps.append, **kwargs)
    return stats, sleeps


def make_article(path: str = "/a", host: str = "news.test") -> NewsArticle:
    return NewsArticle.objects.create(
        source="Test News", title=f"Title {path}", url=f"https://{host}{path}"
    )


def test_robots_agent_name_from_user_agent():
    assert robots_agent_name("KashEngineBot/0.1") == "KashEngineBot"
    standard = "Mozilla/5.0 (compatible; KashEngineBot/0.1; +https://example.com)"
    assert robots_agent_name(standard) == "KashEngineBot"
    assert robots_agent_name("") == "*"


def test_default_user_agent_names_our_bot_and_is_not_a_browser(settings):
    user_agent = settings.NEWS_USER_AGENT
    assert robots_agent_name(user_agent) == "KashEngineBot"
    assert "compatible; KashEngineBot/" in user_agent
    assert "+http" in user_agent  # A contact link.


def test_extract_text_returns_main_text():
    text = extract_text(ARTICLE_HTML, "https://news.test/a")
    assert "benchmark Sensex rose sharply" in text
    assert "Copyright" not in text


def test_extract_text_rejects_short_pages():
    assert len("Subscribe to read.") < MIN_TEXT_CHARS
    assert extract_text("<html><body><p>Subscribe to read.</p></body></html>") == ""


@pytest.mark.django_db
def test_scrape_saves_text():
    article = make_article()
    stats, _ = run(Site(pages={"/a": (200, ARTICLE_HTML)}))

    article.refresh_from_db()
    assert stats == {"scraped": 1, "blocked": 0, "failed": 0, "retry": 0}
    assert "benchmark Sensex rose sharply" in article.text
    assert article.text_scraped_at is not None


@pytest.mark.django_db
def test_robots_txt_disallow_is_obeyed():
    article = make_article("/private/story")
    site = Site(
        robots=(200, "User-agent: *\nDisallow: /private/\n"),
        pages={"/private/story": (200, ARTICLE_HTML)},
    )
    stats, _ = run(site)

    article.refresh_from_db()
    assert stats["blocked"] == 1
    assert "/private/story" not in site.requested  # The page was never requested.
    assert article.text == ""
    assert article.text_scraped_at is not None  # Not tried again.


@pytest.mark.django_db
def test_robots_txt_rule_for_our_bot_name_is_obeyed():
    make_article()
    site = Site(
        robots=(200, "User-agent: KashEngineBot\nDisallow: /\n"),
        pages={"/a": (200, ARTICLE_HTML)},
    )
    stats, _ = run(site)

    assert stats["blocked"] == 1
    assert "/a" not in site.requested


@pytest.mark.django_db
def test_host_is_skipped_when_robots_txt_has_a_server_error():
    article = make_article()
    site = Site(robots=(503, ""), pages={"/a": (200, ARTICLE_HTML)})
    stats, _ = run(site)

    article.refresh_from_db()
    assert stats["blocked"] == 1
    assert "/a" not in site.requested
    assert article.text == ""


@pytest.mark.django_db
def test_robots_txt_is_read_once_for_each_host_and_the_delay_is_used():
    make_article("/a")
    make_article("/b")
    site = Site(pages={"/a": (200, ARTICLE_HTML), "/b": (200, ARTICLE_HTML)})
    stats, sleeps = run(site)

    assert stats["scraped"] == 2
    assert site.requested.count("/robots.txt") == 1
    assert len(sleeps) == 2  # One wait before each of the two articles.
    assert all(2.0 < wait <= 3.0 for wait in sleeps)  # NEWS_SCRAPE_DELAY_SECONDS is 3.


@pytest.mark.django_db
def test_crawl_delay_in_robots_txt_is_used_when_it_is_longer():
    make_article()
    site = Site(
        robots=(200, "User-agent: *\nCrawl-delay: 10\n"),
        pages={"/a": (200, ARTICLE_HTML)},
    )
    _, sleeps = run(site)

    assert max(sleeps) > 9.0


@pytest.mark.django_db
def test_client_error_is_not_tried_again():
    article = make_article()
    stats, _ = run(Site(pages={"/a": (404, "")}))

    article.refresh_from_db()
    assert stats["failed"] == 1
    assert article.text_scraped_at is not None


@pytest.mark.django_db
def test_page_without_enough_text_is_not_tried_again():
    article = make_article()
    stats, _ = run(Site(pages={"/a": (200, "<html><body><p>Subscribe.</p></body></html>")}))

    article.refresh_from_db()
    assert stats["failed"] == 1
    assert article.text == ""
    assert article.text_scraped_at is not None


@pytest.mark.django_db
def test_server_error_is_tried_again_on_the_next_run():
    article = make_article()
    stats, _ = run(Site(pages={"/a": (503, "")}))

    article.refresh_from_db()
    assert stats["retry"] == 1
    assert article.text_scraped_at is None  # Still pending.


@pytest.mark.django_db
def test_old_and_finished_articles_are_not_scraped():
    old = make_article("/old")
    NewsArticle.objects.filter(pk=old.pk).update(fetched_at=timezone.now() - timedelta(days=5))
    done = make_article("/done")
    NewsArticle.objects.filter(pk=done.pk).update(
        text="Already have it.", text_scraped_at=timezone.now()
    )
    site = Site(pages={"/old": (200, ARTICLE_HTML), "/done": (200, ARTICLE_HTML)})

    stats, _ = run(site)

    assert sum(stats.values()) == 0
    assert site.requested == []


@pytest.mark.django_db
def test_limit_is_used():
    for index in range(3):
        make_article(f"/{index}")
    pages = {f"/{index}": (200, ARTICLE_HTML) for index in range(3)}

    stats, _ = run(Site(pages=pages), limit=2)

    assert stats["scraped"] == 2


@pytest.mark.django_db
def test_scrape_can_be_turned_off(settings):
    settings.NEWS_SCRAPE_FULL_TEXT = False
    make_article()
    site = Site(pages={"/a": (200, ARTICLE_HTML)})

    stats, _ = run(site)

    assert stats["disabled"] is True
    assert site.requested == []
