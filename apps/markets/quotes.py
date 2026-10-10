"""Download the daily prices and save them in IndexQuote."""

import logging
from collections.abc import Callable, Iterable
from itertools import pairwise

from .instruments import Instrument, all_instruments
from .models import IndexQuote
from .sources import Bar, QuoteError, fetch_bars

logger = logging.getLogger(__name__)


def save_bars(symbol: str, bars: list[Bar]) -> int:
    """Save the bars of one symbol. Return the number of rows saved.

    The change is from the close of the day before. The oldest bar has no day before, so we
    do not save it. Rows that exist are updated (a bar from the middle of a session becomes the
    final bar at a later run).
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
    """Download all instruments. One symbol that fails does not stop the others.

    Return {"saved": <rows>, "failed": {<symbol>: <error text>}}.
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
