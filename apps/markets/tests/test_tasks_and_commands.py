"""Tests for the market tasks and the management commands."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.markets import tasks
from apps.markets.management.commands import fetch_quotes as fetch_quotes_command
from apps.markets.models import Prediction

from .helpers import MON, SAT, ist, prediction


def test_the_fetch_task_downloads_and_then_checks_the_predictions(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tasks, "fetch_all_quotes", lambda: calls.append("fetch") or {"saved": 3, "failed": {}}
    )
    monkeypatch.setattr(
        tasks, "evaluate_pending", lambda: calls.append("evaluate") or {"evaluated": 1}
    )

    result = tasks.fetch_quotes()

    assert calls == ["fetch", "evaluate"]
    assert result == {"saved": 3, "failed": {}, "evaluation": {"evaluated": 1}}


def test_the_predict_task_skips_the_weekend(monkeypatch):
    monkeypatch.setattr(tasks, "today_ist", lambda: SAT)
    monkeypatch.setattr(tasks, "make_prediction", lambda: pytest.fail("must not run"))

    assert "skipped" in tasks.predict()


def test_the_predict_task_makes_the_prediction_on_a_trading_day(monkeypatch):
    monkeypatch.setattr(tasks, "today_ist", lambda: MON)
    monkeypatch.setattr(
        tasks,
        "make_prediction",
        lambda: (Prediction(target_date=MON, direction="down", confidence=0.55), True),
    )

    assert tasks.predict() == {
        "target_date": "2026-10-05",
        "direction": "down",
        "confidence": 0.55,
        "created": True,
    }


# --- Commands ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_fetch_quotes_command_shows_the_failed_symbols(monkeypatch, capsys):
    monkeypatch.setattr(
        fetch_quotes_command, "fetch_quotes", lambda: {"saved": 5, "failed": {"BZ=F": "no data"}}
    )

    call_command("fetch_quotes")

    out = capsys.readouterr().out
    assert "5 rows saved" in out
    assert "BZ=F: no data" in out
    assert "0 checked, 0 void, 0 waiting" in out


@pytest.mark.django_db
def test_predict_market_command_prints_the_prediction(capsys):
    call_command("predict_market", "--date", "2026-10-05")

    out = capsys.readouterr().out
    assert "Prediction for 2026-10-05: FLAT" in out
    assert "Note: No scored news articles." in out
    assert "not a probability" in out
    assert Prediction.objects.get().target_date == MON


@pytest.mark.django_db
def test_predict_market_command_does_not_change_an_old_prediction(capsys):
    call_command("predict_market", "--date", "2026-10-05")
    capsys.readouterr()

    call_command("predict_market", "--date", "2026-10-05")
    assert "exists already" in capsys.readouterr().out

    call_command("predict_market", "--date", "2026-10-05", "--force")
    assert "exists already" not in capsys.readouterr().out


def test_predict_market_command_rejects_a_bad_date():
    with pytest.raises(CommandError, match="YYYY-MM-DD"):
        call_command("predict_market", "--date", "05/10/2026")


@pytest.mark.django_db
def test_prediction_stats_command_without_results(capsys):
    call_command("prediction_stats")

    assert "No results yet" in capsys.readouterr().out


def add_results(correct: int, wrong: int) -> None:
    for index in range(correct + wrong):
        day = MON + timedelta(days=index)
        is_right = index < correct
        prediction(
            day,
            "up",
            0.5,
            actual_direction="up" if is_right else "down",
            correct=is_right,
            evaluated_at=ist(day, 17),
        )


@pytest.mark.django_db
def test_prediction_stats_command_warns_when_there_are_few_results(capsys):
    add_results(3, 1)

    call_command("prediction_stats")

    out = capsys.readouterr().out
    assert "Accuracy:          3/4 (75%)" in out
    assert "Baseline:" in out
    assert "Only 4 results" in out


@pytest.mark.django_db
def test_prediction_stats_command_says_when_the_baseline_wins(capsys):
    # 15 right, 15 wrong. The most common real result is "up" (15 of 30): accuracy equals baseline.
    add_results(15, 15)

    call_command("prediction_stats")

    out = capsys.readouterr().out
    assert "do not beat the baseline" in out
    assert "Only" not in out
