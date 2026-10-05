"""Tests for the check of the predictions and for the accuracy numbers."""

from datetime import timedelta

import pytest

from apps.markets.evaluation import (
    MIN_RESULTS_TO_TRUST,
    accuracy_stats,
    classify_change,
    evaluate_pending,
)
from apps.markets.models import Prediction

from .helpers import MON, TUE, ist, prediction, quote

NSEI = "^NSEI"


def test_classify_change_uses_the_flat_band():
    assert classify_change(0.26) == "up"
    assert classify_change(0.25) == "flat"
    assert classify_change(0.0) == "flat"
    assert classify_change(-0.25) == "flat"
    assert classify_change(-0.26) == "down"


def test_classify_change_uses_the_setting_and_an_own_band(settings):
    settings.MARKET_FLAT_BAND_PCT = 1.0
    assert classify_change(0.9) == "flat"
    assert classify_change(1.1) == "up"
    assert classify_change(0.9, band=0.1) == "up"


# --- evaluate_pending ----------------------------------------------------------------------


@pytest.mark.django_db
def test_a_final_quote_gives_a_correct_result():
    saved = prediction(MON, "up")
    quote(NSEI, MON, 1.2, saved_at=ist(MON, 16))

    stats = evaluate_pending(now=ist(MON, 16, 30))

    saved.refresh_from_db()
    assert stats == {"evaluated": 1, "void": 0, "waiting": 0}
    assert saved.actual_direction == "up"
    assert saved.actual_change_pct == 1.2
    assert saved.correct is True
    assert saved.evaluated_at == ist(MON, 16, 30)


@pytest.mark.django_db
def test_a_wrong_prediction_and_a_flat_day():
    wrong = prediction(MON, "up")
    flat = prediction(TUE, "flat")
    quote(NSEI, MON, -1.0, saved_at=ist(MON, 16))
    quote(NSEI, TUE, 0.1, saved_at=ist(TUE, 16))

    evaluate_pending(now=ist(TUE, 17))

    wrong.refresh_from_db()
    flat.refresh_from_db()
    assert (wrong.actual_direction, wrong.correct) == ("down", False)
    assert (flat.actual_direction, flat.correct) == ("flat", True)


@pytest.mark.django_db
def test_a_quote_from_the_middle_of_the_session_is_not_final():
    saved = prediction(MON, "up")
    row = quote(NSEI, MON, 1.2, saved_at=ist(MON, 12))

    assert evaluate_pending(now=ist(MON, 12, 30)) == {"evaluated": 0, "void": 0, "waiting": 1}
    saved.refresh_from_db()
    assert saved.evaluated_at is None

    # The quote is saved again after the close. Now it is final.
    type(row).objects.filter(pk=row.pk).update(updated_at=ist(MON, 15, 45))
    assert evaluate_pending(now=ist(MON, 16))["evaluated"] == 1


@pytest.mark.django_db
def test_the_quote_is_final_ten_minutes_after_the_close():
    first = prediction(MON, "up")
    second = prediction(TUE, "up")
    quote(NSEI, MON, 1.0, saved_at=ist(MON, 15, 39))
    quote(NSEI, TUE, 1.0, saved_at=ist(TUE, 15, 40))

    evaluate_pending(now=ist(TUE, 18))

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.evaluated_at is None
    assert second.evaluated_at is not None


@pytest.mark.django_db
def test_a_prediction_for_the_future_is_not_touched():
    saved = prediction(TUE, "up")
    quote(NSEI, TUE, 1.0, saved_at=ist(TUE, 16))

    assert evaluate_pending(now=ist(MON, 20)) == {"evaluated": 0, "void": 0, "waiting": 0}
    saved.refresh_from_db()
    assert saved.evaluated_at is None


@pytest.mark.django_db
def test_no_session_is_void_when_a_later_quote_exists():
    saved = prediction(MON, "up")
    quote(NSEI, TUE, 0.5, saved_at=ist(TUE, 16))  # There is no quote for MON.

    stats = evaluate_pending(now=ist(TUE, 17))

    saved.refresh_from_db()
    assert stats == {"evaluated": 0, "void": 1, "waiting": 0}
    assert saved.evaluated_at is not None
    assert saved.correct is None
    assert saved.actual_direction == ""


@pytest.mark.django_db
def test_a_missing_quote_waits_when_there_is_no_later_quote():
    prediction(MON, "up")
    quote("^GSPC", TUE, 1.0)  # Another symbol does not count.

    assert evaluate_pending(now=ist(TUE, 17)) == {"evaluated": 0, "void": 0, "waiting": 1}


@pytest.mark.django_db
def test_a_quote_without_a_change_waits():
    prediction(MON, "up")
    quote(NSEI, MON, None, saved_at=ist(MON, 16))

    assert evaluate_pending(now=ist(MON, 17))["waiting"] == 1


@pytest.mark.django_db
def test_a_second_run_does_not_change_the_result():
    prediction(MON, "up")
    quote(NSEI, MON, 1.0, saved_at=ist(MON, 16))
    evaluate_pending(now=ist(MON, 17))

    assert evaluate_pending(now=ist(MON, 18)) == {"evaluated": 0, "void": 0, "waiting": 0}
    assert Prediction.objects.get().evaluated_at == ist(MON, 17)


# --- accuracy_stats ------------------------------------------------------------------------


def result(index: int, predicted: str, actual: str, confidence: float = 0.5) -> Prediction:
    day = MON + timedelta(days=index)
    return prediction(
        day,
        predicted,
        confidence,
        actual_direction=actual,
        correct=predicted == actual,
        evaluated_at=ist(day, 17),
    )


@pytest.mark.django_db
def test_accuracy_stats_without_results():
    stats = accuracy_stats()

    assert stats["total"] == 0
    assert stats["accuracy"] is None
    assert stats["baseline_direction"] is None
    assert stats["baseline_accuracy"] is None
    assert stats["enough_results"] is False


@pytest.mark.django_db
def test_accuracy_stats_counts_and_the_baseline():
    result(0, "up", "up", 0.8)
    result(1, "up", "down", 0.7)
    result(2, "flat", "flat", 0.4)
    result(3, "up", "up", 0.5)
    prediction(MON + timedelta(days=4), "up")  # No result yet.
    prediction(  # A void prediction. It has no result and is not counted.
        MON + timedelta(days=5), "up", evaluated_at=ist(MON + timedelta(days=5), 17)
    )

    stats = accuracy_stats()

    assert stats["total"] == 4
    assert stats["correct"] == 3
    assert stats["accuracy"] == 0.75
    assert stats["actual_counts"] == {"up": 2, "down": 1, "flat": 1}
    assert stats["baseline_direction"] == "up"
    assert stats["baseline_accuracy"] == 0.5
    assert stats["by_prediction"]["up"] == {"n": 3, "correct": 2}
    assert stats["by_prediction"]["flat"] == {"n": 1, "correct": 1}
    assert stats["by_prediction"]["down"] == {"n": 0, "correct": 0}
    assert stats["high_confidence"] == {"n": 2, "correct": 1}
    assert stats["recent"] == {"n": 4, "correct": 3}
    assert stats["pending"] == 1
    assert stats["void"] == 1
    assert stats["enough_results"] is False


@pytest.mark.django_db
def test_enough_results_after_thirty():
    for index in range(MIN_RESULTS_TO_TRUST):
        result(index, "up", "up")

    stats = accuracy_stats()

    assert stats["enough_results"] is True
    assert stats["recent"]["n"] == 30
