"""Get the IPO listing price from Yahoo Finance.

The listing price is the open price of the first trading day. We try the NSE symbol (SYMBOL.NS)
first, then the BSE code (CODE.BO).

yfinance is not an official Yahoo tool and is for personal use only (see apps/markets/sources.py).
This code was NOT tested against the live service. If Yahoo returns no price, the IPO stays
without one and we try again until IPO_LISTING_CHECK_DAYS pass. You can also set the price with
`update_ipo --listing-price`.
"""

import logging
import math
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

from apps.markets.sources import QuoteError
from apps.markets.trading import today_ist
from apps.siteconfig import conf

from .collect import compute_status, listing_gain_from_price
from .models import Ipo

logger = logging.getLogger(__name__)

SEARCH_WINDOW_DAYS = 6  # We look for the first bar in this many days after the listing date.


def fetch_listing_open(symbol: str, listing_date: date) -> Decimal:
    """Return the open price of the first trading day on or after listing_date.

    Raises:
        QuoteError: If Yahoo has no usable price bar.
    """
    import yfinance as yf  # noqa: PLC0415  # slow import, only this function needs it

    try:
        frame = yf.Ticker(symbol).history(
            start=listing_date.isoformat(),
            end=(listing_date + timedelta(days=SEARCH_WINDOW_DAYS + 1)).isoformat(),
            interval="1d",
            auto_adjust=False,
            timeout=20,
            raise_errors=True,
        )
    except Exception as exc:  # yfinance raises many kinds of errors: network, rate limit, parse.
        raise QuoteError(f"{symbol}: {exc}") from exc

    if frame is None or frame.empty or "Open" not in frame:
        raise QuoteError(f"{symbol}: no data")

    for stamp, price in frame["Open"].items():
        if stamp.date() < listing_date:
            continue
        if not math.isnan(price) and price > 0:
            return Decimal(str(round(float(price), 2)))
    raise QuoteError(f"{symbol}: no valid open price")


def yahoo_symbols(ipo: Ipo) -> list[str]:
    """Return the Yahoo symbols to try for an IPO, the NSE one first."""
    symbols = []
    if ipo.nse_symbol:
        symbols.append(f"{ipo.nse_symbol}.NS")
    if ipo.bse_code:
        symbols.append(f"{ipo.bse_code}.BO")
    return symbols


def listing_candidates(today: date):
    """Return the IPOs that listed lately and have no result yet."""
    oldest = today - timedelta(days=conf.IPO_LISTING_CHECK_DAYS)
    return Ipo.objects.filter(
        listing_price__isnull=True,
        listing_gain_pct__isnull=True,
        listing_date__isnull=False,
        listing_date__lte=today,
        listing_date__gte=oldest,
    )


def fill_listing_results(
    today: date | None = None,
    fetch: Callable[[str, date], Decimal] | None = None,
) -> dict:
    """Set the listing price and the gain of IPOs that have listed.

    Returns:
        Counts with keys "filled", "waiting" (no price yet) and "no_code" (no exchange code).
    """
    today = today or today_ist()
    fetch = fetch or fetch_listing_open
    stats = {"filled": 0, "waiting": 0, "no_code": 0}

    for ipo in listing_candidates(today):
        symbols = yahoo_symbols(ipo)
        if not symbols:
            stats["no_code"] += 1
            continue

        price = None
        for symbol in symbols:
            try:
                price = fetch(symbol, ipo.listing_date)
                break
            except QuoteError as exc:
                logger.info("No listing price for %s yet: %s", ipo.name, exc)
        if price is None:
            stats["waiting"] += 1
            continue

        ipo.listing_price = price
        ipo.listing_gain_pct = listing_gain_from_price(ipo)
        ipo.status = compute_status(ipo, today)
        ipo.save()
        stats["filled"] += 1
        logger.info("Listing price of %s: %s (%s)", ipo.name, price, ipo.listing_gain_pct)
    return stats
