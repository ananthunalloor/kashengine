"""Tests for the prediction rule and for saving the prediction."""

import pytest

from apps.markets.instruments import global_cues
from apps.markets.models import Prediction
from apps.markets.prediction import (
    DOWN,
    FLAT,
    UP,
    CueReading,
    NewsSignal,
    cue_signal,
    decide,
    global_score,
    make_prediction,
    news_signal,
    news_window_start,
    read_cues,
)

from .helpers import FRI, MON, NEXT_MON, PREV_FRI, SAT, TUE, TUE_AFTER, article, ist, quote

pytestmark = pytest.mark.django_db  # The cues are in the database.

CONFIG = {"news_weight": 0.5, "threshold": 0.15, "min_articles": 5}


def all_cues(good: float) -> list[CueReading]:
    """All the cues, with the same effect on India. +1 means that every cue is good for India."""
    return [
        CueReading(
            c.symbol, c.name, 0.0, FRI, c.weight, good if c.weight > 0 else -good
        )
        for c in global_cues()
    ]  # fmt: skip


def run(news_score, articles, readings, **overrides: float):
    config = {**CONFIG, **overrides}
    return decide(
        NewsSignal(news_score, articles),
        readings,
        news_weight=config["news_weight"],
        threshold=config["threshold"],
        min_articles=int(config["min_articles"]),
    )


def test_cue_signal_is_cut_to_one():
    assert cue_signal(1.0, 2.0) == 0.5
    assert cue_signal(9.0, 2.0) == 1.0
    assert cue_signal(-9.0, 2.0) == -1.0


def test_global_score_respects_the_sign_of_the_weight():
    # Oil (weight < 0) goes up a lot and the S&P 500 is flat: that is bad for India.
    readings = [
        CueReading("^GSPC", "S&P", 0.0, FRI, 0.30, 0.0),
        CueReading("BZ=F", "Brent", 3.0, FRI, -0.15, 1.0),
    ]
    assert global_score(readings) == pytest.approx(-0.15 / 0.45)
    assert global_score([]) is None


def test_good_news_and_good_global_cues_give_up_with_a_high_confidence():
    outcome = run(0.6, 10, all_cues(0.6))

    assert outcome.direction == UP
    assert outcome.score == pytest.approx(0.6)
    assert outcome.coverage == pytest.approx(1.0)
    assert outcome.confidence == pytest.approx(0.8)
    assert outcome.notes == []


def test_bad_news_and_bad_global_cues_give_down():
    outcome = run(-0.6, 10, all_cues(-0.6))

    assert outcome.direction == DOWN
    assert outcome.score == pytest.approx(-0.6)
    assert outcome.confidence == pytest.approx(0.8)


def test_a_score_near_zero_gives_flat():
    outcome = run(0.0, 10, all_cues(0.0))

    assert outcome.direction == FLAT
    assert outcome.confidence == pytest.approx(0.5)


def test_the_threshold_is_inclusive_on_both_sides():
    assert run(0.15, 10, []).direction == UP
    assert run(-0.15, 10, []).direction == DOWN
    assert run(0.14, 10, []).direction == FLAT


def test_a_disagreement_lowers_the_confidence_and_adds_a_note():
    outcome = run(0.8, 10, all_cues(-0.2))

    assert outcome.direction == UP
    assert outcome.confidence == pytest.approx(0.5)  # 0.6 minus 0.1.
    assert any("different directions" in note for note in outcome.notes)


def test_a_small_disagreement_is_not_penalised():
    outcome = run(0.8, 10, all_cues(-0.05))

    assert not any("different directions" in note for note in outcome.notes)


def test_no_data_gives_flat_with_the_lowest_confidence():
    outcome = run(None, 0, [])

    assert (outcome.direction, outcome.confidence, outcome.score) == (FLAT, 0.1, 0.0)
    assert outcome.coverage == 0.0
    assert len(outcome.notes) == 2


def test_few_articles_count_less_and_lower_the_confidence():
    full = run(0.9, 5, [])
    few = run(0.9, 1, [])

    assert few.direction == UP
    assert few.coverage == pytest.approx(0.1)
    assert few.confidence < full.confidence
    assert any("Only 1 scored articles" in note for note in few.notes)


def test_without_news_the_global_cues_decide_alone():
    outcome = run(None, 0, all_cues(0.5))

    assert outcome.direction == UP
    assert outcome.score == pytest.approx(0.5)
    assert outcome.coverage == pytest.approx(0.5)
    assert "No scored news articles." in outcome.notes


def test_a_missing_cue_is_noted_and_counts_less():
    only_one = [CueReading("^GSPC", "S&P", 1.0, FRI, 0.30, 0.5)]
    outcome = run(None, 0, only_one)

    assert outcome.coverage == pytest.approx(0.5 * 0.30)
    assert any("Only 1 of 7 global cues" in note for note in outcome.notes)


def test_confidence_stays_inside_its_limits():
    assert 0.05 <= run(1.0, 100, all_cues(1.0)).confidence <= 0.9
    assert 0.05 <= run(0.0, 1, []).confidence <= 0.9


def test_news_signal_is_the_average_weighted_by_relevance():
    since = ist(FRI, 15, 30)
    article(1, 1.0, 1.0, published_at=ist(SAT, 8))
    article(2, -1.0, 0.5, published_at=ist(SAT, 9))

    signal = news_signal(since)

    assert signal.articles == 2
    assert signal.score == pytest.approx((1.0 - 0.5) / 1.5)


def test_news_signal_ignores_old_unscored_and_not_relevant_articles():
    since = ist(FRI, 15, 30)
    article(1, 1.0, 1.0, published_at=ist(FRI, 14))  # Before the window.
    article(2, 1.0, 1.0, published_at=ist(SAT, 8), scored=False)  # Not scored.
    article(3, 1.0, 0.1, published_at=ist(SAT, 8))  # Not relevant.
    article(4, None, 1.0, published_at=ist(SAT, 8))  # No score.

    signal = news_signal(since)

    assert signal.score is None
    assert signal.articles == 0


def test_news_signal_uses_the_fetch_time_when_there_is_no_publish_time():
    since = ist(FRI, 15, 30)
    article(1, 0.4, 1.0, published_at=None, fetched_at=ist(SAT, 8))
    article(2, 0.9, 1.0, published_at=None, fetched_at=ist(FRI, 10))  # Too old.

    signal = news_signal(since)

    assert signal.articles == 1
    assert signal.score == pytest.approx(0.4)


def test_the_news_window_starts_at_the_last_close_before_the_target_day():
    assert news_window_start(MON) == ist(PREV_FRI, 15, 30)
    assert news_window_start(TUE) == ist(MON, 15, 30)
    assert news_window_start(NEXT_MON) == ist(FRI, 15, 30)


def test_read_cues_takes_the_latest_recent_quote_for_each_cue():
    quote("^GSPC", FRI, 1.0)
    quote("^GSPC", FRI.replace(day=8), -1.0)  # An older quote of the same symbol.
    quote("BZ=F", FRI, 3.0)
    quote("^IXIC", TUE_AFTER, 2.0)  # After the target day. It must not be used.

    readings = {r.symbol: r for r in read_cues(NEXT_MON)}

    assert set(readings) == {"^GSPC", "BZ=F"}
    assert readings["^GSPC"].change_pct == 1.0
    assert readings["^GSPC"].as_of == FRI
    assert readings["^GSPC"].signal == pytest.approx(0.5)  # 1.0 / scale 2.0
    assert readings["BZ=F"].weight < 0


def test_read_cues_skips_old_quotes_and_quotes_without_a_change():
    quote("^GSPC", PREV_FRI, 1.0)  # Ten days before the target. Too old.
    quote("^N225", FRI, None)

    assert read_cues(NEXT_MON) == []


def seed_good_data():
    for cue in global_cues():
        quote(cue.symbol, FRI, 1.0 * (1 if cue.weight > 0 else -1) * cue.scale)
    for number in range(6):
        article(number, 0.8, 1.0, published_at=ist(SAT, 8))


def test_make_prediction_saves_the_result_and_all_the_inputs():
    seed_good_data()

    prediction, created = make_prediction(now=ist(SAT, 7))

    assert created is True
    assert prediction.target_date == NEXT_MON  # Saturday: the next trading day is Monday.
    assert prediction.direction == UP
    assert prediction.news_articles == 6
    assert prediction.news_score == pytest.approx(0.8)
    assert prediction.global_score == pytest.approx(1.0)
    assert 0.05 <= prediction.confidence <= 0.9
    inputs = prediction.inputs
    assert len(inputs["cues"]) == len(global_cues())
    assert inputs["settings"] == CONFIG
    assert inputs["news_window_start"] == ist(FRI, 15, 30).isoformat()
    assert inputs["coverage"] == pytest.approx(1.0)


def test_on_a_trading_day_the_target_is_today():
    prediction, _ = make_prediction(now=ist(MON, 7))

    assert prediction.target_date == MON


def test_make_prediction_without_data_saves_flat_with_notes():
    prediction, created = make_prediction(MON, now=ist(MON, 7))

    assert created
    assert prediction.direction == FLAT
    assert prediction.confidence == 0.1
    assert prediction.news_score is None
    assert prediction.global_score is None
    assert prediction.inputs["notes"]


def test_a_second_run_does_not_change_the_prediction():
    seed_good_data()
    first, _ = make_prediction(NEXT_MON, now=ist(NEXT_MON, 7))
    article(99, -1.0, 1.0, published_at=ist(NEXT_MON, 8))

    second, created = make_prediction(NEXT_MON, now=ist(NEXT_MON, 9))

    assert created is False
    assert second.pk == first.pk
    assert second.news_articles == 6
    assert Prediction.objects.count() == 1


def test_force_makes_it_again_until_the_result_is_known():
    seed_good_data()
    make_prediction(NEXT_MON, now=ist(NEXT_MON, 7))
    for number in range(100, 130):
        article(number, -1.0, 1.0, published_at=ist(NEXT_MON, 8))

    again, created = make_prediction(NEXT_MON, now=ist(NEXT_MON, 9), force=True)

    assert created is True
    assert again.news_articles == 36
    assert again.news_score < 0.8
    assert Prediction.objects.count() == 1

    Prediction.objects.filter(pk=again.pk).update(evaluated_at=ist(NEXT_MON, 16))
    final, created = make_prediction(NEXT_MON, now=ist(NEXT_MON, 17), force=True)
    assert created is False
    assert final.news_articles == 36
