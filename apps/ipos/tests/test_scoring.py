"""Tests for the IPO score, the verdict, and the result numbers."""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.ipos.models import Ipo
from apps.ipos.scoring import (
    GOOD,
    MIXED,
    UNKNOWN,
    WEAK,
    Signal,
    decide,
    gmp_signal,
    ipo_stats,
    likely_good_ipos,
    news_signal,
    score_ipo,
    score_ipos,
    subscription_signal,
)
from apps.news.models import NewsArticle

from .helpers import NOW, TODAY, make_ipo, set_stamps

D = Decimal
GOOD_LIMIT, WEAK_LIMIT = 0.3, 0.1


# --- The signals ---------------------------------------------------------------------------


def test_gmp_signal_is_cut_to_one():
    assert gmp_signal(15) == 0.5
    assert gmp_signal(60) == 1.0
    assert gmp_signal(-45) == -1.0
    assert gmp_signal(0) == 0.0


def test_subscription_signal_uses_a_log_scale():
    assert subscription_signal(1) == 0.0
    assert subscription_signal(50) == 1.0
    assert subscription_signal(500) == 1.0
    assert subscription_signal(50**0.5) == pytest.approx(0.5)
    assert subscription_signal(0.5) == pytest.approx(-0.1772, abs=1e-3)
    assert subscription_signal(0) == -1.0


# --- The rule ------------------------------------------------------------------------------


def run(*signals, notes=()):
    return decide(list(signals), list(notes), GOOD_LIMIT, WEAK_LIMIT)


def test_two_strong_signals_give_good():
    outcome = run(Signal("gmp", 18, 0.6), Signal("subscription", 60, 1.0))

    assert outcome.verdict == GOOD
    assert outcome.score == pytest.approx((0.45 * 0.6 + 0.40) / 0.85, abs=1e-4)
    assert outcome.coverage == pytest.approx(0.85)


def test_the_limits_are_inclusive_for_good_and_exclusive_for_weak():
    assert run(Signal("gmp", 9, 0.3)).verdict == GOOD
    assert run(Signal("gmp", 8, 0.29)).verdict == MIXED
    assert run(Signal("gmp", 3, 0.1)).verdict == MIXED
    assert run(Signal("gmp", 2, 0.09)).verdict == WEAK
    assert run(Signal("gmp", -10, -0.33)).verdict == WEAK


def test_without_the_gmp_and_the_subscription_there_is_no_verdict():
    outcome = run(Signal("news", 0.9, 0.9), notes=["No GMP."])

    assert outcome.verdict == UNKNOWN
    assert outcome.score is None
    assert outcome.coverage == 0.0
    assert any("no verdict" in note for note in outcome.notes)
    assert run().verdict == UNKNOWN


def test_news_counts_less_with_few_articles():
    full = run(Signal("gmp", 0, 0.0), Signal("news", 1.0, 1.0, strength=1.0))
    thin = run(Signal("gmp", 0, 0.0), Signal("news", 1.0, 1.0, strength=1 / 3))

    assert thin.score < full.score
    assert thin.coverage < full.coverage


def test_the_news_can_move_a_verdict_but_not_make_one():
    only_gmp = run(Signal("gmp", 15, 0.5))
    with_bad_news = run(Signal("gmp", 15, 0.5), Signal("news", -1.0, -1.0))

    assert only_gmp.verdict == GOOD
    assert with_bad_news.verdict == MIXED


# --- One IPO -------------------------------------------------------------------------------


def make_article(title: str, score=0.8, relevance=1.0, days_ago=1, number=[0]) -> NewsArticle:  # noqa: B006
    number[0] += 1
    article = NewsArticle.objects.create(
        source="Test",
        title=title,
        url=f"https://t.test/{number[0]}",
        sentiment_score=score,
        relevance=relevance,
        scored_at=NOW,
    )
    NewsArticle.objects.filter(pk=article.pk).update(fetched_at=NOW - timedelta(days=days_ago))
    return article


@pytest.mark.django_db
def test_a_fresh_gmp_gives_a_verdict():
    ipo = set_stamps(make_ipo(gmp=D("20")))

    outcome = score_ipo(ipo, NOW)

    assert outcome.verdict == GOOD
    assert [s.name for s in outcome.signals] == ["gmp"]
    assert outcome.signals[0].value == 20.0


@pytest.mark.django_db
def test_an_old_gmp_is_not_used():
    ipo = set_stamps(make_ipo(gmp=D("20")), gmp_at=NOW - timedelta(hours=100))

    outcome = score_ipo(ipo, NOW)

    assert outcome.verdict == UNKNOWN
    assert any("GMP is old" in note for note in outcome.notes)


@pytest.mark.django_db
def test_a_gmp_without_a_price_band_is_explained():
    ipo = set_stamps(make_ipo(gmp=D("20"), price_band_high=None))

    outcome = score_ipo(ipo, NOW)

    assert outcome.verdict == UNKNOWN
    assert any("price band is not" in note for note in outcome.notes)


@pytest.mark.django_db
def test_a_negative_gmp_gives_weak():
    ipo = set_stamps(make_ipo(gmp=D("-5")))

    assert score_ipo(ipo, NOW).verdict == WEAK


@pytest.mark.django_db
def test_the_subscription_is_used_only_when_it_is_final():
    early = set_stamps(
        make_ipo("Early Ltd", subscription_times=D("80"), close_date=TODAY + timedelta(days=2))
    )
    last_day = set_stamps(
        make_ipo(
            "Lastday Ltd",
            subscription_times=D("80"),
            open_date=TODAY - timedelta(days=2),
            close_date=TODAY,
        )
    )

    early_outcome = score_ipo(early, NOW)
    last_outcome = score_ipo(last_day, NOW)

    assert early_outcome.verdict == UNKNOWN
    assert any("not final" in note for note in early_outcome.notes)
    assert last_outcome.verdict == GOOD
    assert last_outcome.signals[0].name == "subscription"


@pytest.mark.django_db
def test_an_old_subscription_number_is_not_used():
    ipo = set_stamps(
        make_ipo(subscription_times=D("80"), close_date=TODAY),
        subscription_at=NOW - timedelta(days=10),
    )

    assert score_ipo(ipo, NOW).verdict == UNKNOWN


@pytest.mark.django_db
def test_news_that_names_the_ipo_is_a_signal():
    ipo = set_stamps(make_ipo("Acme Foods Limited", gmp=D("9")))
    make_article("Acme Foods IPO opens today", score=-0.9)
    make_article("Other Company wins order", score=0.9)  # Does not name the IPO.
    make_article("Acme Foods Limited IPO old news", score=0.9, days_ago=30)  # Too old.
    make_article("Acme Foods IPO not relevant", score=0.9, relevance=0.1)

    outcome = score_ipo(ipo, NOW)

    assert [s.name for s in outcome.signals] == ["gmp", "news"]
    news = outcome.signals[1]
    assert news.value == pytest.approx(-0.9)
    assert news.strength == pytest.approx(1 / 3)
    assert outcome.score < 0.3  # Bad news pulled the score down.


@pytest.mark.django_db
def test_news_matches_whole_names_only_and_ignores_short_names():
    make_article("Acme Foodstuffs report profit")
    make_article("Om news today")

    assert news_signal(make_ipo("Acme Foods Limited"), NOW) is None
    assert news_signal(make_ipo("Om Limited", open_date=TODAY + timedelta(days=1)), NOW) is None


# --- All the IPOs --------------------------------------------------------------------------


@pytest.mark.django_db
def test_score_ipos_saves_the_score_and_all_the_inputs():
    good = set_stamps(make_ipo("Good Ltd", gmp=D("25")))
    nodata = make_ipo("Nodata Ltd")

    stats = score_ipos(NOW)

    good.refresh_from_db()
    nodata.refresh_from_db()
    assert stats == {"scored": 1, "unknown": 1}
    assert good.verdict == GOOD
    assert good.score == pytest.approx(0.8333, abs=1e-3)
    assert good.scored_at == NOW
    assert good.score_inputs["signals"][0]["name"] == "gmp"
    assert good.score_inputs["settings"] == {"good": 0.3, "weak": 0.1}
    assert (nodata.verdict, nodata.score) == (UNKNOWN, None)
    assert nodata.score_inputs["notes"]


@pytest.mark.django_db
def test_a_listed_ipo_keeps_its_last_score():
    listed = set_stamps(
        make_ipo(
            "Listed Ltd",
            gmp=D("25"),
            status=Ipo.Status.LISTED,
            listing_gain_pct=30.0,
            verdict=WEAK,
            score=0.05,
        )
    )

    assert score_ipos(NOW) == {"scored": 0, "unknown": 0}
    listed.refresh_from_db()
    assert (listed.verdict, listed.score) == (WEAK, 0.05)


@pytest.mark.django_db
def test_an_old_ipo_is_not_scored():
    make_ipo("Old Ltd", open_date=TODAY - timedelta(days=45), close_date=None)

    assert score_ipos(NOW) == {"scored": 0, "unknown": 0}


@pytest.mark.django_db
def test_likely_good_ipos_lists_the_good_ones_best_first():
    set_stamps(make_ipo("B Good Ltd", gmp=D("15")))
    set_stamps(make_ipo("A Better Ltd", gmp=D("30")))
    set_stamps(make_ipo("Weak Ltd", gmp=D("0")))
    make_ipo("No Data Ltd")
    score_ipos(NOW)

    names = [ipo.name for ipo in likely_good_ipos(TODAY)]

    assert names == ["A Better Ltd", "B Good Ltd"]


# --- Results -------------------------------------------------------------------------------


def listed(name, gain, verdict):
    return make_ipo(
        name,
        open_date=TODAY - timedelta(days=10),
        status=Ipo.Status.LISTED,
        listing_gain_pct=gain,
        verdict=verdict,
    )


@pytest.mark.django_db
def test_ipo_stats_without_results():
    stats = ipo_stats()

    assert stats["listed"] == 0
    assert stats["baseline"] is None
    assert stats["enough_results"] is False


@pytest.mark.django_db
def test_ipo_stats_counts_the_verdicts_and_the_baseline():
    listed("A Ltd", 15.0, GOOD)
    listed("B Ltd", 12.0, GOOD)
    listed("C Ltd", 4.0, GOOD)
    listed("D Ltd", -2.0, WEAK)
    listed("E Ltd", 30.0, UNKNOWN)  # No verdict before the listing: only in the baseline.
    listed("F Ltd", 8.0, "")
    make_ipo("Pending Ltd", open_date=TODAY + timedelta(days=1))

    stats = ipo_stats()

    assert stats["listed"] == 6
    assert stats["judged"] == 4
    assert stats["without_verdict"] == 2
    assert stats["baseline"] == pytest.approx(3 / 6)  # 15, 12, and 30 did well.
    assert stats["by_verdict"][GOOD]["n"] == 3
    assert stats["by_verdict"][GOOD]["did_well"] == 2
    assert stats["by_verdict"][GOOD]["average_gain"] == pytest.approx(31 / 3)
    assert stats["by_verdict"][WEAK] == {"n": 1, "did_well": 0, "average_gain": -2.0}
    assert stats["by_verdict"][MIXED]["average_gain"] is None
    assert stats["enough_results"] is False
