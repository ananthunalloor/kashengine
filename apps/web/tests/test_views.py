"""Tests for the pages. They use the test client and the database."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.companies.models import Company
from apps.delivery.models import DeliveryLog
from apps.ipos.models import Ipo
from apps.markets.models import IndexQuote, Prediction
from apps.news.models import NewsArticle
from apps.reports.models import Report

pytestmark = pytest.mark.django_db

IST = ZoneInfo("Asia/Kolkata")
DS = {"Datastar-Request": "true"}

PAGES = [
    "web:dashboard",
    "web:reports",
    "web:news",
    "web:ipos",
    "web:markets",
    "web:companies",
    "web:delivery",
]


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(  # ty: ignore[unresolved-attribute]  # Django manager
        "anan",
        password="pass-123-word",
    )


@pytest.fixture
def client_in(client, user):
    client.force_login(user)
    return client


def article(title, score=None, source="Mint", **kwargs) -> NewsArticle:
    kwargs.setdefault("url", f"https://news.test/{abs(hash(title))}")
    kwargs.setdefault("published_at", timezone.now())
    if score is not None:
        kwargs.setdefault("sentiment_score", score)
        kwargs.setdefault("relevance", 0.9)
        kwargs.setdefault("scored_at", timezone.now())
        kwargs.setdefault("sentiment_reason", f"Reason for {title}")
    return NewsArticle.objects.create(title=title, source=source, **kwargs)


@pytest.mark.parametrize("name", PAGES)
def test_every_page_needs_a_login(client, name):
    response = client.get(reverse(name))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("web:login"))


def test_the_health_check_and_the_login_page_are_open(client):
    assert client.get("/health/").status_code == 200
    assert client.get(reverse("web:login")).status_code == 200


def test_a_user_can_log_in_and_log_out(client, user):
    response = client.post(reverse("web:login"), {"username": "anan", "password": "pass-123-word"})
    assert response.status_code == 302
    assert response["Location"] == reverse("web:dashboard")
    assert client.get(reverse("web:dashboard")).status_code == 200

    assert client.get(reverse("web:logout")).status_code == 405  # Logout needs a POST.
    assert client.post(reverse("web:logout")).status_code == 302
    assert client.get(reverse("web:dashboard")).status_code == 302


def test_a_wrong_password_shows_an_error(client, user):
    response = client.post(reverse("web:login"), {"username": "anan", "password": "wrong"})

    assert response.status_code == 200
    assert "not correct" in response.text


def test_the_admin_still_has_its_own_login(client):
    response = client.get("/admin/")

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


@pytest.mark.parametrize("name", PAGES)
def test_every_page_works_with_no_data(client_in, name):
    response = client_in.get(reverse(name))

    assert response.status_code == 200
    assert 'aria-current="page"' in response.text or name == "web:dashboard"


def make_prediction(day=date(2026, 10, 8), direction="up", confidence=0.52, **kwargs):
    kwargs.setdefault("score", 0.3)
    return Prediction.objects.create(
        target_date=day,
        direction=direction,
        confidence=confidence,
        news_score=0.31,
        global_score=-0.12,
        news_articles=24,
        inputs={
            "cues": [
                {
                    "name": "S&P 500",
                    "change_pct": 1.2,
                    "as_of": "2026-10-07",
                    "weight": 0.3,
                    "signal": 0.6,
                },
                {
                    "name": "Brent crude",
                    "change_pct": -2.0,
                    "as_of": "2026-10-07",
                    "weight": -0.15,
                    "signal": -0.6,
                },
            ],
            "notes": ["Few articles: the news score counts less."],
        },
        **kwargs,
    )


def test_the_dashboard_shows_the_outlook(client_in):
    make_prediction()
    IndexQuote.objects.create(symbol="^NSEI", day=date(2026, 10, 7), close=25000.5, change_pct=0.8)

    text = client_in.get(reverse("web:dashboard")).text

    assert "The Nifty 50 is likely to rise." in text
    assert "Moderate signal." in text
    assert "52%" in text
    assert "from 24 articles" in text
    assert "S&amp;P 500" in text
    assert "Few articles" in text
    assert "Nifty 50" in text
    assert "25,000" in text or "25000.50" in text


@pytest.mark.parametrize(
    ("direction", "phrase"),
    [("down", "likely to fall"), ("flat", "likely to stay flat")],
)
def test_the_dashboard_words_for_each_direction(client_in, direction, phrase):
    make_prediction(direction=direction)

    assert phrase in client_in.get(reverse("web:dashboard")).text


def test_the_dashboard_without_a_prediction_says_what_to_do(client_in):
    text = client_in.get(reverse("web:dashboard")).text

    assert "No outlook yet" in text
    assert "predict_market" in text


def test_the_dashboard_shows_the_track_record_and_the_latest_report(client_in):
    make_prediction(
        date(2026, 10, 6),
        correct=True,
        actual_direction="up",
        actual_change_pct=0.7,
        evaluated_at=timezone.now(),
    )
    Report.objects.create(date=date(2026, 10, 7), text="x")

    text = client_in.get(reverse("web:dashboard")).text

    assert "right on 1 of 1 days" in text
    assert reverse("web:report", args=["2026-10-07"]) in text


def test_the_dashboard_shows_stories_and_ipos(client_in):
    article("RBI cuts rates and banks rally", 0.8)
    article("Refinery fire hurts oil stocks", -0.7)
    today = timezone.localdate()
    Ipo.objects.create(
        name="Acme Foods Limited",
        open_date=today,
        close_date=today + timedelta(days=2),
        price_band_high=Decimal("100"),
        status="open",
        verdict="good",
        score=0.5,
    )

    text = client_in.get(reverse("web:dashboard")).text

    assert "RBI cuts rates" in text
    assert "Refinery fire" in text
    assert text.count("Acme Foods Limited") == 1  # It is "likely good" and open: one line only.
    assert f"Closes {(today + timedelta(days=2)):%-d %b}" in text


def test_the_report_list_and_detail(client_in):
    first = Report.objects.create(
        date=date(2026, 10, 6), text="Old report", prediction="down", confidence=0.3
    )
    second = Report.objects.create(
        date=date(2026, 10, 7), text="Line one\nLine two", prediction="up", confidence=0.6
    )
    DeliveryLog.objects.create(
        report=second, channel="telegram", status="failed", recipient="1", error="Chat not found"
    )

    listing = client_in.get(reverse("web:reports")).text
    detail = client_in.get(reverse("web:report", args=["2026-10-07"])).text

    assert listing.index("7 October") < listing.index("6 October")  # The newest first.
    assert "Line one\nLine two" in detail
    assert "Chat not found" in detail
    assert reverse("web:report", args=[first.date]) in detail  # The link to the older report.


def test_a_report_that_does_not_exist_gives_404(client_in):
    assert client_in.get(reverse("web:report", args=["2026-10-07"])).status_code == 404


def test_a_date_that_is_not_real_gives_404(client_in):
    assert client_in.get("/reports/2026-02-30/").status_code == 404


def test_the_report_text_is_escaped(client_in):
    Report.objects.create(date=date(2026, 10, 7), text="<script>alert(1)</script>")

    text = client_in.get(reverse("web:report", args=["2026-10-07"])).text

    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;" in text


def test_news_filters_by_search_score_and_source(client_in):
    article("Bank profits jump", 0.7, source="Mint")
    article("Bank fraud found", -0.6, source="Hindu")
    article("Bank holiday notice", 0.0, source="Mint")
    article("Waiting for a score", None, source="Mint")
    url = reverse("web:news")

    everything = client_in.get(url).text
    positive = client_in.get(url, {"sentiment": "positive"}).text
    negative = client_in.get(url, {"sentiment": "negative"}).text
    neutral = client_in.get(url, {"sentiment": "neutral"}).text
    unscored = client_in.get(url, {"sentiment": "unscored"}).text
    hindu = client_in.get(url, {"source": "Hindu"}).text
    search = client_in.get(url, {"q": "holiday"}).text

    assert "4 articles" in everything
    assert "Bank profits jump" in positive
    assert "Bank fraud" not in positive
    assert "Bank fraud found" in negative
    assert "Bank profits" not in negative
    assert "Bank holiday notice" in neutral
    assert "Bank profits" not in neutral
    assert "Waiting for a score" in unscored
    assert "Bank holiday" not in unscored
    assert "Bank fraud found" in hindu
    assert "Bank profits" not in hindu
    assert "1 article" in search
    assert "Bank holiday notice" in search


def test_a_datastar_request_gets_only_the_list(client_in):
    article("Bank profits jump", 0.7)
    article("Steel demand falls", -0.5)
    signals = '{"q": "steel", "sentiment": "", "source": "", "page": "1"}'

    response = client_in.get(reverse("web:news"), {"datastar": signals}, headers=DS)

    assert response["Content-Type"].startswith("text/html")
    assert response.text.lstrip().startswith('<div id="news-results">')
    assert "<html" not in response.text
    assert "Steel demand falls" in response.text
    assert "Bank profits" not in response.text


def test_the_full_page_has_the_filter_form_and_the_datastar_script(client_in, settings):
    settings.DATASTAR_SRC = "/static/vendor/datastar.js"
    article("Bank profits jump", 0.7)

    text = client_in.get(reverse("web:news"), {"q": "bank"}).text

    assert "data-bind:q" in text
    assert "data-on:input__debounce.300ms" in text
    assert 'src="/static/vendor/datastar.js"' in text
    assert 'value="bank"' in text
    assert "&quot;q&quot;: &quot;bank&quot;" in text  # The starting signals, escaped.


def test_news_pages(client_in, settings):
    settings.WEB_PAGE_SIZE = 2
    for i in range(5):
        article(f"Story number {i}", 0.5, published_at=timezone.now() - timedelta(minutes=i))

    url = reverse("web:news")
    first = client_in.get(url).text
    last = client_in.get(url, {"page": 3}).text
    beyond = client_in.get(url, {"page": 99}).text  # A page too far gives the last page.

    assert "Story number 0" in first
    assert "Story number 2" not in first
    assert "Page 1 of 3" in first
    assert "Story number 4" in last
    assert "Story number 4" in beyond
    assert "page=2" in first  # A link that works without JavaScript.


def test_news_text_is_escaped(client_in):
    article("<b>Bold</b> title", 0.5, sentiment_reason="<img src=x onerror=alert(1)>")

    text = client_in.get(reverse("web:news")).text

    assert "<b>Bold</b>" not in text
    assert "<img src=x" not in text


@pytest.fixture
def ipos():
    today = timezone.localdate()
    make = Ipo.objects.create
    return {
        "open": make(
            name="Open Foods Limited",
            open_date=today,
            close_date=today + timedelta(days=2),
            price_band_high=Decimal("100"),
            gmp=Decimal("20"),
            status="open",
            verdict="good",
            score=0.6,
            category="mainboard",
        ),
        "soon": make(
            name="Soon Tools Limited",
            open_date=today + timedelta(days=3),
            close_date=today + timedelta(days=5),
            status="upcoming",
            category="sme",
        ),
        "done": make(
            name="Done Steel Limited",
            open_date=today - timedelta(days=20),
            close_date=today - timedelta(days=17),
            listing_date=today - timedelta(days=14),
            price_band_high=Decimal("100"),
            listing_price=Decimal("120"),
            listing_gain_pct=20.0,
            status="listed",
            verdict="good",
        ),
    }


def test_the_ipo_list_shows_active_ipos_first_and_hides_listed(client_in, ipos):
    text = client_in.get(reverse("web:ipos")).text

    assert text.index("Open Foods") < text.index("Soon Tools")
    assert "Done Steel" not in text
    assert "+20.0%" in text  # The GMP of Open Foods: 20 on 100.


def test_the_ipo_tabs_and_filters(client_in, ipos):
    url = reverse("web:ipos")

    listed = client_in.get(url, {"status": "listed"}).text
    everything = client_in.get(url, {"status": "all"}).text
    sme = client_in.get(url, {"status": "all", "category": "sme"}).text
    unknown = client_in.get(url, {"status": "all", "verdict": "unknown"}).text
    good = client_in.get(url, {"status": "all", "verdict": "good"}).text
    search = client_in.get(url, {"status": "all", "q": "steel"}).text

    assert "Done Steel" in listed
    assert "Open Foods" not in listed
    assert "+20.0%" in listed  # The listing gain.
    assert "3 IPOs" in everything
    assert "Soon Tools" in sme
    assert "Open Foods" not in sme
    assert "Soon Tools" in unknown
    assert "Open Foods" not in unknown
    assert "Open Foods" in good
    assert "Done Steel" in good
    assert "Soon Tools" not in good
    assert "1 IPO" in search


def test_a_datastar_request_for_ipos_gets_only_the_list(client_in, ipos):
    signals = '{"q": "", "status": "listed", "verdict": "", "category": "", "page": "1"}'

    response = client_in.get(reverse("web:ipos"), {"datastar": signals}, headers=DS)

    assert response.text.lstrip().startswith('<div id="ipo-results">')
    assert "Done Steel" in response.text
    assert "<html" not in response.text


def test_an_unknown_status_filter_falls_back_to_active(client_in, ipos):
    text = client_in.get(reverse("web:ipos"), {"status": "nonsense"}).text

    assert "Open Foods" in text
    assert "Done Steel" not in text


def test_the_ipo_detail_page(client_in, ipos):
    ipo = ipos["open"]
    ipo.score_inputs = {
        "signals": [
            {"name": "gmp", "value": 20.0, "signal": 0.67, "strength": 1.0},
            {"name": "subscription", "value": 12.5, "signal": 0.64, "strength": 1.0},
            {"name": "news", "value": 0.4, "signal": 0.4, "strength": 0.33},
        ],
        "notes": ["No subscription number."],
    }
    ipo.gmp_updated_at = timezone.now() - timedelta(hours=5)
    ipo.save()

    text = client_in.get(reverse("web:ipo", args=[ipo.pk])).text

    assert "Open Foods Limited" in text
    assert "+20.0%" in text
    assert "12.5x" in text
    assert "No subscription number." in text
    assert "updated 5 hours ago" in text
    assert "₹100" in text


def test_the_detail_page_of_an_ipo_without_a_score(client_in):
    ipo = Ipo.objects.create(name="Bare Limited")

    text = client_in.get(reverse("web:ipo", args=[ipo.pk])).text

    assert "There is no usable signal yet." in text
    assert client_in.get(reverse("web:ipo", args=[999999])).status_code == 404


def test_the_markets_page_shows_history_and_the_result(client_in):
    make_prediction(
        date(2026, 10, 6),
        correct=True,
        actual_direction="up",
        actual_change_pct=0.7,
        evaluated_at=timezone.now(),
    )
    make_prediction(
        date(2026, 10, 7),
        direction="down",
        correct=False,
        actual_direction="up",
        actual_change_pct=0.2,
        evaluated_at=timezone.now(),
    )
    make_prediction(date(2026, 10, 8))

    text = client_in.get(reverse("web:markets")).text

    assert "of <span" in text  # The numbers are in their own tags.
    assert "(<span" in text
    assert "Right" in text
    assert "Wrong" in text
    assert "Waiting" in text
    assert text.index("Thu 8 Oct") < text.index("Tue 6 Oct")


def test_the_companies_page_searches_by_name_symbol_and_sector(client_in):
    Company.objects.create(name="Infosys Limited", symbol="INFY", sector="IT services")
    Company.objects.create(
        name="HDFC Bank Limited",
        symbol="HDFCBANK",
        sector="Banks",
        last_updated=datetime(2026, 10, 1, tzinfo=IST),
    )
    url = reverse("web:companies")

    assert "2 companies" in client_in.get(url).text
    assert "Infosys" in client_in.get(url, {"q": "infy"}).text
    assert "HDFC" in client_in.get(url, {"q": "banks"}).text
    nothing = client_in.get(url, {"q": "zzz"}).text
    assert "No company matches." in nothing


def test_a_datastar_request_for_companies_gets_only_the_list(client_in):
    Company.objects.create(name="Infosys Limited", symbol="INFY")

    response = client_in.get(reverse("web:companies"), {"datastar": '{"q": "info"}'}, headers=DS)

    assert response.text.lstrip().startswith('<div id="company-results">')
    assert "Infosys" in response.text


def test_the_delivery_page(client_in, settings):
    settings.TELEGRAM_CHAT_IDS = ["111", "222"]
    report = Report.objects.create(date=date(2026, 10, 7), text="x")
    DeliveryLog.objects.create(report=report, channel="telegram", status="sent", recipient="111")
    DeliveryLog.objects.create(
        channel="telegram", status="failed", recipient="222", error="Forbidden: bot was blocked"
    )

    text = client_in.get(reverse("web:delivery")).text

    assert "2 Telegram chats" in text
    assert "bot was blocked" in text
    assert "Test" in text  # A log without a report is a test message.
    assert "111" not in text  # We do not show chat IDs.
    assert "222" not in text
