"""Tests for saving the quotes."""

import pytest

from apps.markets.instruments import ALL_INSTRUMENTS, GLOBAL_CUES, TOTAL_CUE_WEIGHT, Instrument
from apps.markets.models import IndexQuote
from apps.markets.quotes import fetch_quotes, save_bars
from apps.markets.sources import Bar, QuoteError

from .helpers import FRI, MON, TUE, WED

pytestmark = pytest.mark.django_db


def test_the_instrument_weights_add_up_to_one():
    assert pytest.approx(1.0) == TOTAL_CUE_WEIGHT
    assert len({i.symbol for i in ALL_INSTRUMENTS}) == len(ALL_INSTRUMENTS)
    assert all(cue.scale > 0 for cue in GLOBAL_CUES)


def test_save_bars_saves_the_change_from_the_day_before():
    bars = [Bar(MON, 100.0), Bar(TUE, 102.0), Bar(WED, 99.96)]

    assert save_bars("^NSEI", bars) == 2  # The oldest bar has no day before.

    rows = {row.day: row for row in IndexQuote.objects.filter(symbol="^NSEI")}
    assert set(rows) == {TUE, WED}
    assert rows[TUE].change_pct == pytest.approx(2.0)
    assert rows[WED].change_pct == pytest.approx(-2.0)
    assert rows[WED].close == 99.96


def test_save_bars_updates_a_row_that_exists():
    save_bars("X", [Bar(MON, 100.0), Bar(TUE, 101.0)])
    save_bars("X", [Bar(MON, 100.0), Bar(TUE, 103.0)])  # The final close replaces the first one.

    row = IndexQuote.objects.get(symbol="X", day=TUE)
    assert IndexQuote.objects.count() == 1
    assert row.close == 103.0
    assert row.change_pct == pytest.approx(3.0)


def test_save_bars_with_one_bar_saves_nothing():
    assert save_bars("X", [Bar(MON, 100.0)]) == 0
    assert save_bars("X", []) == 0
    assert IndexQuote.objects.count() == 0


def test_save_bars_handles_unsorted_bars_and_double_days():
    bars = [Bar(TUE, 102.0), Bar(MON, 100.0), Bar(MON, 100.0)]

    assert save_bars("X", bars) == 1
    assert IndexQuote.objects.get().change_pct == pytest.approx(2.0)


def test_one_failed_symbol_does_not_stop_the_others():
    instruments = [Instrument("A", "A"), Instrument("B", "B"), Instrument("C", "C")]

    def source(symbol):
        if symbol == "B":
            raise QuoteError("B: no data")
        return [Bar(MON, 100.0), Bar(FRI, 110.0)]

    result = fetch_quotes(source, instruments)

    assert result == {"saved": 2, "failed": {"B": "B: no data"}}
    assert set(IndexQuote.objects.values_list("symbol", flat=True)) == {"A", "C"}
