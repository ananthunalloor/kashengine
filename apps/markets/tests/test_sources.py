"""Tests for fetch_bars. A fake yfinance module is used. There is no network."""

import sys
import types
from datetime import date

import pandas as pd
import pytest

from apps.markets.sources import Bar, QuoteError, fetch_bars


def install_fake_yfinance(monkeypatch, frame=None, error=None):
    calls = []

    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, **kwargs):
            calls.append((self.symbol, kwargs))
            if error:
                raise error
            return frame

    module = types.ModuleType("yfinance")
    module.Ticker = Ticker
    monkeypatch.setitem(sys.modules, "yfinance", module)
    return calls


def make_frame(stamps, closes, tz="Asia/Kolkata"):
    index = pd.DatetimeIndex(stamps, tz=tz)
    return pd.DataFrame({"Close": closes}, index=index)


def test_fetch_bars_returns_sorted_bars_and_uses_the_local_date(monkeypatch):
    # Midnight in India is the day before in UTC. The bar must keep the Indian date.
    frame = make_frame(["2026-10-06", "2026-10-05"], [101.5, 100.0])
    calls = install_fake_yfinance(monkeypatch, frame)

    bars = fetch_bars("^NSEI", period="5d")

    assert bars == [Bar(date(2026, 10, 5), 100.0), Bar(date(2026, 10, 6), 101.5)]
    symbol, kwargs = calls[0]
    assert symbol == "^NSEI"
    assert kwargs["period"] == "5d"
    assert kwargs["interval"] == "1d"
    assert kwargs["raise_errors"] is True


def test_fetch_bars_skips_missing_and_zero_prices(monkeypatch):
    frame = make_frame(["2026-10-05", "2026-10-06", "2026-10-07"], [100.0, float("nan"), 0.0])
    install_fake_yfinance(monkeypatch, frame)

    assert fetch_bars("X") == [Bar(date(2026, 10, 5), 100.0)]


def test_the_last_bar_wins_when_two_bars_have_the_same_day(monkeypatch):
    frame = make_frame(["2026-10-05 09:15", "2026-10-05 15:30"], [100.0, 105.0])
    install_fake_yfinance(monkeypatch, frame)

    assert fetch_bars("X") == [Bar(date(2026, 10, 5), 105.0)]


@pytest.mark.parametrize(
    "frame",
    [None, pd.DataFrame(), pd.DataFrame({"Open": [1.0]}, index=pd.DatetimeIndex(["2026-10-05"]))],
)
def test_no_data_raises_quote_error(monkeypatch, frame):
    install_fake_yfinance(monkeypatch, frame)

    with pytest.raises(QuoteError, match="no data"):
        fetch_bars("X")


def test_only_bad_prices_raise_quote_error(monkeypatch):
    install_fake_yfinance(monkeypatch, make_frame(["2026-10-05"], [float("nan")]))

    with pytest.raises(QuoteError, match="no valid prices"):
        fetch_bars("X")


def test_any_yfinance_error_becomes_quote_error(monkeypatch):
    install_fake_yfinance(monkeypatch, error=RuntimeError("rate limited"))

    with pytest.raises(QuoteError, match=r"\^NSEI: rate limited"):
        fetch_bars("^NSEI")
