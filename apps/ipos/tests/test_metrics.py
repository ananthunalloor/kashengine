"""Tests for the metrics step, the new task, and the refresh_ipo_data command."""

from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.ipos import metrics, tasks
from apps.ipos.gmp import GmpResult, GmpSourceError
from apps.ipos.models import Ipo

from .helpers import make_ipo

pytestmark = pytest.mark.django_db


@pytest.fixture
def steps(monkeypatch):
    """Replace the two network steps. The list shows which ones ran."""
    ran = []

    def fake_gmp():
        ran.append("gmp")
        return GmpResult(rows=2, matched=1, updated=1)

    def fake_listing():
        ran.append("listing")
        return {"filled": 0, "waiting": 0, "no_code": 0}

    monkeypatch.setattr(metrics, "update_gmp", fake_gmp)
    monkeypatch.setattr(metrics, "fill_listing_results", fake_listing)
    return ran


def test_the_gmp_step_is_off_by_default_and_the_listing_step_is_on(settings, steps):
    settings.IPO_GMP_ENABLED = False
    settings.IPO_LISTING_ENABLED = True

    result = metrics.refresh_metrics()

    assert steps == ["listing"]
    assert result["gmp"] == "disabled"
    assert result["scores"] == {"scored": 0, "unknown": 0}


def test_force_runs_both_steps(settings, steps):
    settings.IPO_GMP_ENABLED = False
    settings.IPO_LISTING_ENABLED = False

    result = metrics.refresh_metrics(force=True)

    assert steps == ["gmp", "listing"]
    assert result["gmp"]["updated"] == 1


def test_a_failed_gmp_step_does_not_stop_the_rest(settings, monkeypatch, steps):
    settings.IPO_GMP_ENABLED = True

    def broken():
        raise GmpSourceError("the page changed")

    monkeypatch.setattr(metrics, "update_gmp", broken)

    result = metrics.refresh_metrics()

    assert result["gmp"] == {"error": "the page changed"}
    assert steps == ["listing"]
    assert "scores" in result


def test_a_broken_listing_step_does_not_stop_the_scores(settings, monkeypatch, steps):
    settings.IPO_LISTING_ENABLED = True

    def broken():
        raise RuntimeError("yfinance broke")

    monkeypatch.setattr(metrics, "fill_listing_results", broken)

    result = metrics.refresh_metrics()

    assert result["listing"] == {"error": "see the log"}
    assert "scores" in result


def test_the_new_gmp_updates_the_score(settings, monkeypatch):
    settings.IPO_GMP_ENABLED = True
    settings.IPO_LISTING_ENABLED = False
    ipo = make_ipo("Acme Foods Limited")

    def fake_gmp():
        ipo.gmp = Decimal("30")
        ipo.save()
        return GmpResult(rows=1, matched=1, updated=1)

    monkeypatch.setattr(metrics, "update_gmp", fake_gmp)

    metrics.refresh_metrics()

    ipo.refresh_from_db()
    assert ipo.verdict == Ipo.Verdict.GOOD


def test_the_refresh_task_runs_the_metrics(steps):
    result = tasks.refresh_ipo_metrics()

    assert "listing" in result
    assert steps == ["listing"]


def test_the_command_shows_the_gmp_result(monkeypatch, capsys):
    result = GmpResult(rows=5, matched=2, updated=1, unchanged=1)
    result.unmatched = ["Old One", "Old Two", "Old Three"]
    monkeypatch.setattr(
        "apps.ipos.management.commands.refresh_ipo_data.update_gmp", lambda **kw: result
    )

    call_command("refresh_ipo_data", "--force")

    out = capsys.readouterr().out
    assert "5 rows. 2 match a saved IPO: 1 updated, 1 unchanged" in out
    assert "3 rows match no saved IPO" in out
    assert "Old One" in out
    assert "Listing results: 0 filled" in out  # --force also runs the listing step.


def test_the_command_shows_a_gmp_error_and_goes_on(settings, monkeypatch, capsys):
    def broken(**kw):
        raise GmpSourceError("no GMP table found. The columns that we saw: A, B")

    monkeypatch.setattr("apps.ipos.management.commands.refresh_ipo_data.update_gmp", broken)

    call_command("refresh_ipo_data", "--force")

    out = capsys.readouterr().out
    assert "Failed: no GMP table found" in out
    assert "Scores:" in out


def test_the_command_does_nothing_for_the_gmp_when_it_is_off(settings, capsys):
    settings.IPO_GMP_ENABLED = False
    settings.IPO_LISTING_ENABLED = False

    call_command("refresh_ipo_data")

    out = capsys.readouterr().out
    assert "The GMP fetch is off" in out
    assert "The listing step is off" in out
