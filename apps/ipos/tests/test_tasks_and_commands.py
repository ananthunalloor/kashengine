"""Tests for the IPO tasks and the management commands."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.ipos import tasks
from apps.ipos.management.commands import collect_ipos as collect_command
from apps.ipos.models import Ipo
from apps.markets.trading import today_ist

pytestmark = pytest.mark.django_db

D = Decimal


def open_ipo(name="Acme Foods Limited", **kwargs) -> Ipo:
    """An IPO that is open today. The commands use the real date, so we do too."""
    today = today_ist()
    kwargs.setdefault("open_date", today)
    kwargs.setdefault("close_date", today + timedelta(days=2))
    kwargs.setdefault("price_band_high", D("100"))
    return Ipo.objects.create(name=name, **kwargs)


def test_the_collect_task_does_not_fetch_when_the_fetch_is_off(monkeypatch, settings):
    settings.IPO_FETCH_ENABLED = False
    monkeypatch.setattr(tasks, "collect_ipos", lambda: pytest.fail("must not fetch"))
    open_ipo()

    result = tasks.collect()

    assert result["fetch"] == "disabled"
    assert result["scores"] == {"scored": 0, "unknown": 1}


def test_the_collect_task_fetches_then_scores_when_the_fetch_is_on(monkeypatch, settings):
    settings.IPO_FETCH_ENABLED = True
    calls = []
    monkeypatch.setattr(tasks, "collect_ipos", lambda: calls.append("fetch") or {"created": 1})
    monkeypatch.setattr(
        tasks, "refresh_metrics", lambda: calls.append("metrics") or {"scores": {"scored": 0}}
    )

    result = tasks.collect()

    assert calls == ["fetch", "metrics"]  # The metrics step does the status and the scores.
    assert result["fetch"] == {"created": 1}
    assert result["scores"] == {"scored": 0}


def test_the_score_task_updates_the_status_and_scores():
    open_ipo(gmp=D("30"))

    assert tasks.score() == {"scored": 1, "unknown": 0}


def test_collect_command_when_the_fetch_is_off(capsys, settings):
    settings.IPO_FETCH_ENABLED = False

    call_command("collect_ipos")

    out = capsys.readouterr().out
    assert "fetch is off" in out
    assert "Scores:" in out


def test_collect_command_shows_failed_pages(monkeypatch, capsys):
    monkeypatch.setattr(
        collect_command,
        "collect_ipos",
        lambda: {
            "created": 2,
            "updated": 1,
            "unchanged": 0,
            "skipped": 3,
            "failed": {"u": "u: boom"},
        },
    )

    call_command("collect_ipos", "--force")

    out = capsys.readouterr().out
    assert "2 new, 1 updated" in out
    assert "Failed: u: boom" in out


def test_import_csv_command(tmp_path, capsys):
    path = tmp_path / "ipos.csv"
    today = today_ist().isoformat()
    path.write_text(
        f"name,open_date,price_band_high,gmp\nCsv Foods Ltd,{today},100,30\n", encoding="utf-8"
    )

    call_command("import_ipo_csv", str(path))

    out = capsys.readouterr().out
    assert "1 new" in out
    assert Ipo.objects.get().verdict == "good"


def test_import_csv_command_turns_errors_into_command_errors(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("name,gmp\nA Ltd,abc\n", encoding="utf-8")

    with pytest.raises(CommandError, match="Line 2"):
        call_command("import_ipo_csv", str(bad))
    with pytest.raises(CommandError):
        call_command("import_ipo_csv", str(tmp_path / "missing.csv"))


def test_update_ipo_sets_the_gmp_and_shows_the_verdict(capsys):
    ipo = open_ipo()

    call_command("update_ipo", "acme", "--gmp", "25")

    ipo.refresh_from_db()
    out = capsys.readouterr().out
    assert ipo.gmp == D("25")
    assert ipo.gmp_updated_at is not None
    assert "Verdict now: good" in out
    assert ipo.verdict == "good"  # The score is saved at once.
    assert ipo.score is not None


def test_update_ipo_confirms_an_unchanged_gmp():
    ipo = open_ipo(gmp=D("25"))
    old = Ipo.objects.get(pk=ipo.pk).gmp_updated_at

    call_command("update_ipo", "acme", "--gmp", "25")

    assert Ipo.objects.get(pk=ipo.pk).gmp_updated_at > old


def test_update_ipo_listing_price_gives_the_result(capsys):
    today = today_ist()
    ipo = open_ipo(
        open_date=today - timedelta(days=8),
        close_date=today - timedelta(days=5),
        listing_date=today,
    )

    call_command("update_ipo", "acme", "--listing-price", "130")

    ipo.refresh_from_db()
    assert ipo.status == "listed"
    assert ipo.listing_gain_pct == pytest.approx(30.0)
    assert "Gain at the listing: +30.0%" in capsys.readouterr().out


def test_update_ipo_errors():
    open_ipo("Acme Foods Limited")
    open_ipo("Acme Steel Limited", open_date=today_ist() + timedelta(days=1))

    with pytest.raises(CommandError, match="at least one"):
        call_command("update_ipo", "acme")
    with pytest.raises(CommandError, match="More than one"):
        call_command("update_ipo", "acme", "--gmp", "1")
    with pytest.raises(CommandError, match="No IPO"):
        call_command("update_ipo", "nothing", "--gmp", "1")
    with pytest.raises(CommandError, match="must be a number"):
        call_command("update_ipo", "foods", "--gmp", "lots")


def test_score_ipos_command_shows_a_table(capsys):
    open_ipo("Good Ltd", gmp=D("30"))
    open_ipo("Nodata Ltd")

    call_command("score_ipos")

    out = capsys.readouterr().out
    assert "1 with a verdict, 1 without" in out
    assert "Good Ltd" in out
    assert "good" in out
    assert "not advice" in out


def test_score_ipos_command_with_no_ipo(capsys):
    call_command("score_ipos")

    assert "No IPO to show." in capsys.readouterr().out


def test_ipo_stats_command_without_results(capsys):
    call_command("ipo_stats")

    assert "No results yet" in capsys.readouterr().out


def make_results(count: int, good_gain: float) -> None:
    for number in range(count):
        Ipo.objects.create(
            name=f"Result {number} Ltd",
            open_date=today_ist() - timedelta(days=100 + number),
            status="listed",
            listing_gain_pct=good_gain,
            verdict="good",
        )


def test_ipo_stats_command_warns_when_there_are_few_results(capsys):
    make_results(3, 20.0)

    call_command("ipo_stats")

    out = capsys.readouterr().out
    assert "Baseline: 100%" in out
    assert "3/3 did well" in out
    assert "Only 3 IPOs with a verdict" in out


def test_ipo_stats_command_says_when_good_does_not_beat_the_baseline(capsys):
    make_results(20, 20.0)

    call_command("ipo_stats")

    out = capsys.readouterr().out
    assert "do not beat the baseline" in out
    assert "Only" not in out
