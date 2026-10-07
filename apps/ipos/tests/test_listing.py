"""Tests for the listing price. They do not use the network."""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.ipos import listing
from apps.ipos.listing import fill_listing_results, listing_candidates, yahoo_symbols
from apps.ipos.models import Ipo
from apps.markets.sources import QuoteError

from .helpers import TODAY, make_ipo

pytestmark = pytest.mark.django_db

D = Decimal


def listed_ipo(name="Acme Foods Limited", days_ago=1, **kwargs) -> Ipo:
    kwargs.setdefault("nse_symbol", "ACME")
    kwargs.setdefault("price_band_high", D("100"))
    return make_ipo(
        name,
        open_date=TODAY - timedelta(days=days_ago + 5),
        close_date=TODAY - timedelta(days=days_ago + 2),
        listing_date=TODAY - timedelta(days=days_ago),
        **kwargs,
    )


def test_yahoo_symbols_try_the_nse_symbol_first():
    ipo = Ipo(nse_symbol="ACME", bse_code="544001")

    assert yahoo_symbols(ipo) == ["ACME.NS", "544001.BO"]
    assert yahoo_symbols(Ipo(bse_code="544001")) == ["544001.BO"]
    assert yahoo_symbols(Ipo()) == []


def test_the_listing_price_and_gain_are_saved():
    ipo = listed_ipo()
    calls = []

    def fetch(symbol, day):
        calls.append((symbol, day))
        return D("125.50")

    stats = fill_listing_results(TODAY, fetch)

    ipo.refresh_from_db()
    assert stats == {"filled": 1, "waiting": 0, "no_code": 0}
    assert calls == [("ACME.NS", TODAY - timedelta(days=1))]
    assert ipo.listing_price == D("125.50")
    assert ipo.listing_gain_pct == pytest.approx(25.5)
    assert ipo.status == Ipo.Status.LISTED


def test_the_bse_code_is_the_second_try():
    ipo = listed_ipo(bse_code="544001")

    def fetch(symbol, day):
        if symbol.endswith(".NS"):
            raise QuoteError("no data")
        return D("90")

    fill_listing_results(TODAY, fetch)

    ipo.refresh_from_db()
    assert ipo.listing_price == D("90")
    assert ipo.listing_gain_pct == pytest.approx(-10.0)


def test_an_ipo_without_a_price_yet_stays_open_for_the_next_run():
    ipo = listed_ipo()

    def fetch(symbol, day):
        raise QuoteError("no data")

    stats = fill_listing_results(TODAY, fetch)

    ipo.refresh_from_db()
    assert stats == {"filled": 0, "waiting": 1, "no_code": 0}
    assert ipo.listing_price is None


def test_an_ipo_without_a_code_is_counted():
    listed_ipo(nse_symbol="")

    stats = fill_listing_results(TODAY, lambda s, d: pytest.fail("must not fetch"))

    assert stats == {"filled": 0, "waiting": 0, "no_code": 1}


def test_without_a_price_band_the_price_is_saved_and_the_gain_is_not():
    ipo = listed_ipo(price_band_high=None)

    fill_listing_results(TODAY, lambda s, d: D("120"))

    ipo.refresh_from_db()
    assert ipo.listing_price == D("120")
    assert ipo.listing_gain_pct is None


def test_only_recent_ipos_without_a_result_are_checked(settings):
    settings.IPO_LISTING_CHECK_DAYS = 14
    recent = listed_ipo("Recent Foods Limited", days_ago=3)
    listed_ipo("Old Foods Limited", days_ago=30)
    listed_ipo("Done Foods Limited", days_ago=2, listing_price=D("110"))
    listed_ipo("Gained Foods Limited", days_ago=2, listing_gain_pct=4.0)
    make_ipo("Future Foods Limited", listing_date=TODAY + timedelta(days=3))
    make_ipo("No Date Foods Limited")

    assert list(listing_candidates(TODAY)) == [recent]


def test_fetch_listing_open_reads_the_first_open_price(monkeypatch):
    pd = pytest.importorskip("pandas")
    index = pd.DatetimeIndex(["2026-10-04", "2026-10-05", "2026-10-06"], tz="Asia/Kolkata")
    frame = pd.DataFrame({"Open": [float("nan"), 123.456, 130.0]}, index=index)

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, **kwargs):
            return frame

    yfinance = pytest.importorskip("yfinance")
    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)

    price = listing.fetch_listing_open("ACME.NS", TODAY.replace(day=4))

    assert price == D("123.46")  # The NaN bar is skipped.


def test_fetch_listing_open_raises_quote_error_for_no_data(monkeypatch):
    pd = pytest.importorskip("pandas")
    yfinance = pytest.importorskip("yfinance")

    class FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, **kwargs):
            return pd.DataFrame()

    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)

    with pytest.raises(QuoteError, match="no data"):
        listing.fetch_listing_open("ACME.NS", TODAY)


def test_fetch_listing_open_wraps_library_errors(monkeypatch):
    yfinance = pytest.importorskip("yfinance")

    class FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, **kwargs):
            raise RuntimeError("rate limited")

    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)

    with pytest.raises(QuoteError, match="rate limited"):
        listing.fetch_listing_open("ACME.NS", TODAY)
