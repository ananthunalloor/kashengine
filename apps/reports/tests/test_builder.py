"""Tests for the daily report builder."""

# ruff: noqa: E501, S105  (the test data has long lines and a fake token)
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.companies.models import Company
from apps.ipos.models import Ipo
from apps.markets.models import Prediction
from apps.markets.tests.helpers import ist, prediction, quote
from apps.news.models import NewsArticle
from apps.reports.builder import (
    build_report,
    gather_ipos,
    gather_last_result,
    gather_news,
    gather_prediction,
    gather_track_record,
    render_text,
)
from apps.reports.models import Report

pytestmark = pytest.mark.django_db

DAY = date(2026, 10, 6)  # A Tuesday.
NOW = ist(DAY, 7, 30)
SINCE = ist(date(2026, 10, 5), 15, 30)  # The close before the day.
D = Decimal


def story(number, score, relevance=0.9, title=None, **kwargs) -> NewsArticle:
    kwargs.setdefault("published_at", ist(DAY, 6))
    return NewsArticle.objects.create(
        source="Test News",
        title=title or f"Story {number}",
        url=f"https://t.test/{number}",
        sentiment_score=score,
        relevance=relevance,
        sentiment_reason=kwargs.pop("sentiment_reason", f"Reason {number}."),
        scored_at=NOW,
        **kwargs,
    )


def ipo(name, **kwargs) -> Ipo:
    kwargs.setdefault("price_band_high", D("100"))
    return Ipo.objects.create(name=name, **kwargs)


# --- News ----------------------------------------------------------------------------------


def test_news_picks_the_strongest_good_and_bad_stories():
    story(1, 0.9)
    story(2, 0.5)
    story(3, 0.3)
    story(4, 0.25)  # A fourth good story. The limit is 3.
    story(5, -0.8)
    story(6, -0.4)
    story(7, 0.1)  # Neutral. Not shown.

    news = gather_news(SINCE)

    assert [s["title"] for s in news["good"]] == ["Story 1", "Story 2", "Story 3"]
    assert [s["title"] for s in news["bad"]] == ["Story 5", "Story 6"]
    assert (news["articles"], news["positive"], news["negative"]) == (7, 4, 2)


def test_news_ranks_by_score_times_relevance():
    story(1, 0.9, relevance=0.45)  # 0.405
    story(2, 0.6, relevance=0.95)  # 0.57

    news = gather_news(SINCE, limit=1)

    assert news["good"][0]["title"] == "Story 2"


def test_news_skips_old_unscored_irrelevant_and_double_stories():
    story(1, 0.9, published_at=ist(date(2026, 10, 5), 10))  # Before the close.
    story(2, 0.9, relevance=0.2)  # Not relevant enough (the limit is 0.4).
    story(3, 0.9, title="Same Title")
    story(4, 0.8, title="same  title")  # The same title in other letters.
    NewsArticle.objects.create(source="T", title="Unscored", url="https://t.test/u")

    news = gather_news(SINCE)

    assert [s["title"] for s in news["good"]] == ["Same Title"]
    assert news["articles"] == 2


def test_news_without_a_publish_time_uses_the_fetch_time():
    article = story(1, 0.9, published_at=None)
    NewsArticle.objects.filter(pk=article.pk).update(fetched_at=ist(DAY, 5))

    assert len(gather_news(SINCE)["good"]) == 1


def test_news_item_has_the_reason_the_companies_and_a_short_title():
    article = story(1, 0.9, title="T" * 300, sentiment_reason="R " * 200)
    article.companies.add(
        *[Company.objects.create(name=f"Co {n}", symbol=f"CO{n}") for n in range(5)]
    )

    item = gather_news(SINCE)["good"][0]

    assert len(item["title"]) <= 110
    assert item["title"].endswith("…")
    assert len(item["reason"]) <= 140
    assert len(item["companies"]) == 3
    assert item["url"] == "https://t.test/1"


# --- IPOs ----------------------------------------------------------------------------------


def test_ipos_are_grouped_and_the_verdict_is_shown():
    ipo("Open Ltd", open_date=DAY - timedelta(days=1), close_date=DAY + timedelta(days=1),
        status="open", gmp=D("20"), verdict="good", score=0.7)  # fmt: skip
    ipo("Soon Ltd", open_date=DAY + timedelta(days=3), close_date=DAY + timedelta(days=5),
        status="upcoming")  # fmt: skip
    ipo("Far Ltd", open_date=DAY + timedelta(days=30), close_date=DAY + timedelta(days=32))
    ipo("Lists Ltd", open_date=DAY - timedelta(days=6), close_date=DAY - timedelta(days=3),
        listing_date=DAY, status="closed")  # fmt: skip

    data = gather_ipos(DAY)

    assert [i["name"] for i in data["open_now"]] == ["Open Ltd"]
    assert [i["name"] for i in data["upcoming"]] == ["Soon Ltd"]
    assert [i["name"] for i in data["listing_today"]] == ["Lists Ltd"]
    assert [i["name"] for i in data["likely_good"]] == ["Open Ltd"]
    assert data["open_now"][0]["gmp_pct"] == 20.0
    assert data["without_verdict"] == 1  # "Soon Ltd" has no verdict. "Far Ltd" is not watched.


def test_ipo_lists_are_cut_to_the_limit():
    for n in range(10):
        ipo(f"Open {n} Ltd", open_date=DAY, close_date=DAY + timedelta(days=2))

    assert len(gather_ipos(DAY, limit=4)["open_now"]) == 4


# --- Prediction, last result, track record -------------------------------------------------


def test_gather_prediction_orders_the_cues_by_their_effect_on_the_score():
    saved = prediction(
        DAY,
        "up",
        0.7,
        news_score=0.4,
        news_articles=12,
        global_score=0.5,
        inputs={
            "cues": [
                {
                    "name": "Small",
                    "change_pct": 0.1,
                    "as_of": "2026-10-05",
                    "weight": 0.1,
                    "signal": 0.1,
                },
                {
                    "name": "Big",
                    "change_pct": 2.0,
                    "as_of": "2026-10-05",
                    "weight": 0.3,
                    "signal": 1.0,
                },
                {
                    "name": "Oil",
                    "change_pct": 3.0,
                    "as_of": "2026-10-05",
                    "weight": -0.15,
                    "signal": 1.0,
                },
            ],
            "notes": ["A note."],
        },
    )

    data = gather_prediction(saved)

    assert [c["name"] for c in data["cues"]] == ["Big", "Oil", "Small"]
    assert data["notes"] == ["A note."]
    assert data["direction"] == "up"


def test_last_result_is_the_newest_one_and_not_too_old():
    assert gather_last_result(DAY) is None
    prediction(date(2026, 9, 1), "up", correct=True, actual_direction="up", actual_change_pct=1.0)
    assert gather_last_result(DAY) is None  # Too old.

    prediction(date(2026, 10, 2), "up", correct=False, actual_direction="down",
               actual_change_pct=-0.8)  # fmt: skip
    prediction(date(2026, 10, 5), "down", correct=True, actual_direction="down",
               actual_change_pct=-0.5)  # fmt: skip

    last = gather_last_result(DAY)

    assert last["target_date"] == "2026-10-05"
    assert last["correct"] is True


def test_track_record_numbers():
    assert gather_track_record()["total"] == 0
    prediction(date(2026, 10, 2), "up", correct=True, actual_direction="up")
    prediction(date(2026, 10, 5), "up", correct=False, actual_direction="down")

    record = gather_track_record()

    assert (record["total"], record["correct"], record["accuracy"]) == (2, 1, 0.5)
    assert record["enough_results"] is False


# --- The text ------------------------------------------------------------------------------


def make_data(**overrides) -> dict:
    data = {
        "date": "2026-10-06",
        "prediction": {
            "target_date": "2026-10-06",
            "direction": "up",
            "confidence": 0.62,
            "score": 0.31,
            "news_score": 0.25,
            "news_articles": 14,
            "global_score": 0.4,
            "cues": [{"name": "S&P 500", "change_pct": 0.8, "as_of": "2026-10-05"}],
            "notes": ["Only 3 of 7 global cues are available."],
        },
        "last_result": {
            "target_date": "2026-10-05",
            "direction": "down",
            "actual_direction": "up",
            "actual_change_pct": 0.9,
            "correct": False,
        },
        "track_record": {
            "total": 12,
            "correct": 7,
            "accuracy": 7 / 12,
            "baseline_accuracy": 0.5,
            "enough_results": False,
        },  # fmt: skip
        "news": {
            "since": "x",
            "articles": 20,
            "positive": 8,
            "negative": 5,
            "good": [
                {
                    "title": "Banks gain",
                    "source": "Wire",
                    "score": 0.8,
                    "reason": "Rates fall.",
                    "companies": ["HDFC Bank"],
                    "url": "https://t.test/1",
                }
            ],
            "bad": [
                {
                    "title": "Oil jumps",
                    "source": "Wire",
                    "score": -0.7,
                    "reason": "",
                    "companies": [],
                    "url": "https://t.test/2",
                }
            ],
        },  # fmt: skip
        "ipos": {
            "open_now": [
                {
                    "name": "Acme Foods",
                    "category": "mainboard",
                    "status": "open",
                    "open_date": "2026-10-05",
                    "close_date": "2026-10-08",
                    "listing_date": None,
                    "price_band_low": 95.0,
                    "price_band_high": 100.0,
                    "gmp_pct": 22.0,
                    "subscription_times": None,
                    "verdict": "good",
                    "score": 0.7,
                }
            ],
            "listing_today": [],
            "upcoming": [],
            "likely_good": [{"name": "Acme Foods", "score": 0.7}],
            "without_verdict": 2,
            "days_ahead": 7,
        },  # fmt: skip
    }
    data.update(overrides)
    return data


def test_render_text_shows_all_the_parts():
    text = render_text(make_data())

    assert "KASH ENGINE: DAILY REPORT, Tue 6 Oct 2026" in text
    assert "NIFTY 50 OUTLOOK, Tue 6 Oct" in text
    assert "▲ UP: strong signal (strength 0.62, score +0.31)." in text
    assert "The strength is not a probability." in text
    assert "News: +0.25 from 14 articles. Global markets: +0.40." in text
    assert "Cues: S&P 500 +0.8%" in text
    assert "Note: Only 3 of 7 global cues are available." in text
    assert (
        "Last result (Mon 5 Oct): we said down, the market was up (+0.90%). We were wrong." in text
    )
    assert "Track record: 7 of 12 right (58%). Simple baseline: 50%. Only 12 results." in text
    assert "20 important articles: 8 good, 5 bad, 7 neutral." in text
    assert "• Banks gain (Wire, +0.8)" in text
    assert "Companies: HDFC Bank" in text
    assert "• Oil jumps (Wire, -0.7)" in text
    assert (
        "• Acme Foods (mainboard): ₹95-100, closes Thu 8 Oct, GMP +22%, likely to do well" in text
    )
    assert "Likely to do well (our rule, not a promise):" in text
    assert "2 IPOs have no verdict" in text
    assert text.endswith("It is not investment advice.")
    assert len(text) < 4000


def test_render_text_says_what_is_missing():
    data = make_data(last_result=None)
    data["prediction"].update(news_score=None, global_score=None, cues=[], notes=[],
                              direction="down", confidence=0.3)  # fmt: skip
    data["track_record"] = {"total": 0, "correct": 0, "accuracy": None,
                            "baseline_accuracy": None, "enough_results": False}  # fmt: skip
    data["news"] = {
        "since": "x",
        "articles": 0,
        "positive": 0,
        "negative": 0,
        "good": [],
        "bad": [],
    }
    data["ipos"] = {"open_now": [], "listing_today": [], "upcoming": [], "likely_good": [],
                    "without_verdict": 0, "days_ahead": 7}  # fmt: skip

    text = render_text(data)

    assert "▼ DOWN: weak signal" in text
    assert "News: no scored news. Global markets: no data." in text
    assert "Track record: no results yet." in text
    assert "Last result" not in text
    assert "No scored news. The news or the LLM service may be down." in text
    assert "No IPO is open, listing, or coming in the next 7 days." in text


# --- Saving --------------------------------------------------------------------------------


def test_build_report_saves_the_text_the_prediction_and_the_data():
    story(1, 0.9)
    story(2, -0.7)
    ipo("Open Ltd", open_date=DAY, close_date=DAY + timedelta(days=2), status="open")

    report, created = build_report(DAY, now=NOW)

    assert created
    assert report.date == DAY
    assert report.prediction == Prediction.objects.get().direction
    assert report.confidence == Prediction.objects.get().confidence
    assert "DAILY REPORT, Tue 6 Oct 2026" in report.text
    assert report.data["news"]["articles"] == 2
    assert report.data["ipos"]["open_now"][0]["name"] == "Open Ltd"
    assert Prediction.objects.get().target_date == DAY  # It was made for the report.


def test_build_report_uses_the_prediction_that_exists():
    quote("^GSPC", date(2026, 10, 5), 2.0)
    first = prediction(DAY, "down", 0.77, score=-0.5)

    report, _ = build_report(DAY, now=NOW)

    assert report.prediction == "down"
    assert report.confidence == 0.77
    assert Prediction.objects.get() == first


def test_build_report_on_a_weekend_predicts_the_next_trading_day():
    saturday = date(2026, 10, 10)

    report, _ = build_report(saturday, now=ist(saturday, 9))

    assert report.data["prediction"]["target_date"] == "2026-10-12"


def test_a_second_build_keeps_the_report_and_force_builds_it_again():
    first, created = build_report(DAY, now=NOW)
    assert created
    story(1, 0.9)

    second, created_again = build_report(DAY, now=NOW)
    assert not created_again
    assert second.pk == first.pk
    assert second.data["news"]["articles"] == 0

    third, created_third = build_report(DAY, now=NOW, force=True)
    assert created_third
    assert third.pk == first.pk
    assert third.data["news"]["articles"] == 1
    assert Report.objects.count() == 1


def test_render_text_uses_the_singular_for_one_ipo_without_a_verdict():
    data = make_data()
    data["ipos"]["without_verdict"] = 1

    assert "1 IPO has no verdict" in render_text(data)


def test_build_report_scores_the_ipos_first_so_the_gmp_is_current():
    ipo("Hot Ltd", open_date=DAY, close_date=DAY + timedelta(days=2), gmp=D("30"))

    report, _ = build_report(DAY, now=NOW)

    item = report.data["ipos"]["open_now"][0]
    assert item["verdict"] == "good"
    assert "GMP +30%" in report.text
    assert "Hot Ltd (score +1.00)" in report.text


def test_build_report_still_works_when_the_ipo_scoring_fails(monkeypatch):
    from apps.reports import builder

    def broken(now):
        raise RuntimeError("boom")

    monkeypatch.setattr(builder, "score_ipos", broken)

    report, created = build_report(DAY, now=NOW)

    assert created
    assert "DAILY REPORT" in report.text
