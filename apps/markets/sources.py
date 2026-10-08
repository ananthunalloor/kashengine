"""Download daily prices from Yahoo Finance with the yfinance package.

Legal note: yfinance is not an official Yahoo tool. It uses Yahoo's public APIs "for research and
educational purposes" and "for personal use only". Check the Yahoo terms of use for your case.
We save only the daily close and the change in percent. Do not share the raw prices.

yfinance can break when Yahoo changes something. Then the quotes fail and the log shows why.
"""

import logging
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)


class QuoteError(Exception):
    """We could not get the prices of a symbol."""


@dataclass(frozen=True)
class Bar:
    """The close price of one trading day."""

    day: date  # The local date of the exchange.
    close: float


def fetch_bars(symbol: str, period: str = "1mo") -> list[Bar]:
    """Return the daily closes of a symbol, oldest first. Raise QuoteError if there are none.

    The last bar can be from the middle of a session. The real close replaces it at the next run.
    """
    import yfinance as yf  # noqa: PLC0415  # Slow to import, and only this function needs it.

    try:
        frame = yf.Ticker(symbol).history(
            period=period, interval="1d", auto_adjust=False, timeout=20, raise_errors=True
        )
    except Exception as exc:  # yfinance raises many kinds of errors: network, rate limit, parse.
        raise QuoteError(f"{symbol}: {exc}") from exc

    if frame is None or frame.empty or "Close" not in frame:
        raise QuoteError(f"{symbol}: no data")

    bars: dict[date, Bar] = {}
    for stamp, close in frame["Close"].dropna().items():
        if close > 0:
            # The index has the time zone of the exchange, so .date() is the local trading day.
            bars[stamp.date()] = Bar(stamp.date(), float(close))  # The last one wins.
    if not bars:
        raise QuoteError(f"{symbol}: no valid prices")
    return [bars[day] for day in sorted(bars)]
