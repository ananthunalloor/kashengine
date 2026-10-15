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
    """We could not get the prices of a symbol.

    `fetch_bars` raises this error for every kind of failure. The message starts with the symbol.
    `quotes.fetch_quotes` catches it, so one bad symbol does not stop the other symbols.
    """


@dataclass(frozen=True)
class Bar:
    """The close price of one trading day.

    Attributes:
        day: The trading day, as the local date of the exchange.
        close: The close price. It is always greater than zero.
    """

    day: date  # The local date of the exchange.
    close: float


def fetch_bars(symbol: str, period: str = "1mo") -> list[Bar]:
    """Download the daily closes of a symbol from Yahoo Finance.

    The function makes one network call with yfinance (timeout of 20 seconds). It uses the raw
    close, not the adjusted close. It drops rows without a close and rows with a close of zero or
    less. If the data has two rows for one day, the last row wins.

    Args:
        symbol: The Yahoo Finance symbol, for example `^NSEI`.
        period: The yfinance period text that sets how far back to read, for example `1mo` for
            one month. The interval is always one day.

    Returns:
        A list of `Bar` values, oldest first, with one bar for each trading day. The list is
        never empty.

    Raises:
        QuoteError: When yfinance fails for any reason, when the answer has no data, or when no
            row has a valid price.

    Note:
        The last bar can be from the middle of a session. The real close replaces it at the next
        run.
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
