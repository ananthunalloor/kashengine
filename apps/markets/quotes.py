"""Download the daily prices and save them in `IndexQuote`.

`fetch_quotes` is the entry point. The Celery task `markets.fetch_quotes` and the management
command `fetch_quotes` call it. It reads the symbols from `instruments.py`, gets the bars from
`sources.py` and saves them with `save_bars`.
"""

import logging
from collections.abc import Callable, Iterable
from itertools import pairwise

from .instruments import Instrument, all_instruments
from .models import IndexQuote
from .sources import Bar, QuoteError, fetch_bars

logger = logging.getLogger(__name__)


def save_bars(symbol: str, bars: list[Bar]) -> int:
    """Save the bars of one symbol in `IndexQuote`.

    The change in percent is from the close of the bar before. The oldest bar has no bar before,
    so the function does not save it. Two bars of the same day count as one bar (the last wins).
    The function writes all rows in one upsert on (symbol, day). A row that exists gets a new
    close, a new change and a new `updated_at`. A bar from the middle of a session becomes the
    final bar at a later run.

    Args:
        symbol: The Yahoo Finance symbol of the bars.
        bars: The bars of the symbol, in any order.

    Returns:
        The number of rows that the function wrote. This counts new rows and updated rows.
        It is 0 when there are fewer than two bars.

    Side effects:
        Writes to the `IndexQuote` table. A row is skipped when the close of the bar before is
        zero or less.
    """
    ordered = sorted({bar.day: bar for bar in bars}.values(), key=lambda bar: bar.day)
    rows = [
        IndexQuote(
            symbol=symbol,
            day=bar.day,
            close=bar.close,
            change_pct=(bar.close / previous.close - 1) * 100,
        )
        for previous, bar in pairwise(ordered)
        if previous.close > 0
    ]
    if rows:
        IndexQuote.objects.bulk_create(
            rows,
            update_conflicts=True,
            unique_fields=["symbol", "day"],
            update_fields=["close", "change_pct", "updated_at"],
        )
    return len(rows)


def fetch_quotes(
    source: Callable[[str], list[Bar]] = fetch_bars,
    instruments: Iterable[Instrument] | None = None,
) -> dict:
    """Download the bars of all instruments and save them.

    One symbol that fails does not stop the others. The function logs a warning for each failure.
    Only `QuoteError` is caught. Any other error from `source` stops the run.

    Args:
        source: A function that takes a symbol and returns a list of bars. The default is
            `fetch_bars`. A test can give a fake source.
        instruments: The instruments to download. The default (None) is `all_instruments()`.

    Returns:
        A dict with two keys. `saved` is the total number of rows written (an integer).
        `failed` is a dict that maps each failed symbol to its error text. It is empty when all
        symbols work.

    Side effects:
        Network calls (through `source`) and writes to the `IndexQuote` table.
    """
    instruments = all_instruments() if instruments is None else instruments
    saved = 0
    failed: dict[str, str] = {}
    for instrument in instruments:
        try:
            bars = source(instrument.symbol)
        except QuoteError as exc:
            logger.warning("Quotes failed: %s", exc)
            failed[instrument.symbol] = str(exc)
            continue
        saved += save_bars(instrument.symbol, bars)
    logger.info("Quotes done: %d rows saved, %d symbols failed", saved, len(failed))
    return {"saved": saved, "failed": failed}
