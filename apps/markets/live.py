"""Normalize Upstox V3 full-mode ticks, keep the newest per instrument and broadcast them.

The stream worker (`stream_upstox`) calls `normalize_*` for each decoded feed and `publish` about
once a second. `publish` upserts `LiveSnapshot` rows (bulk, so no model signals fire) and sends one
channel-layer message per group. The WebSocket consumer (`consumers.py`) joins those groups and
reads `LiveSnapshot` for the first frame. Payloads hold public market data only, never tokens.
"""

import asyncio
import logging
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from pydantic import BaseModel, ConfigDict, Field

from .models import LiveSnapshot

logger = logging.getLogger(__name__)
INDEX_GROUP = "live.indices"
STATUS_KEY = "market-status"
DEPTH_LEVELS = 5


def company_group(company_id: int) -> str:
    """Return the channel-layer group of one company (ASCII, as Channels requires).

    Args:
        company_id: The company primary key.

    Returns:
        The group name, for example `live.company.7`.
    """
    return f"live.company.{company_id}"


class Ltpc(BaseModel):
    """Validated last trade fields. `ltt` is the exchange time in milliseconds."""

    model_config = ConfigDict(allow_inf_nan=False)
    ltp: float = Field(gt=0)
    ltt: int = Field(gt=0)
    cp: float | None = Field(default=None, ge=0)


@dataclass(frozen=True)
class Target:
    """One streamed instrument: a company (equity) or an index."""

    kind: str
    name: str
    company_id: int | None = None
    symbol: str = ""


def _number(value) -> float | None:
    """Return a finite float, or None for a missing or invalid value.

    Args:
        value: A number or numeric text from the feed.

    Returns:
        The finite float, or None.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _iso(milliseconds: int) -> str:
    """Return an exchange time in ms as an ISO 8601 UTC text.

    Args:
        milliseconds: Milliseconds since the Unix epoch.

    Returns:
        The ISO 8601 text.
    """
    return datetime.fromtimestamp(milliseconds / 1000, UTC).isoformat()


def _day_ohlc(feed: dict) -> dict:
    """Pick the `1d` bar of a `marketOHLC` block, or an empty dict.

    Args:
        feed: A `marketFF` or `indexFF` block.

    Returns:
        The day bar, or an empty dict.
    """
    for bar in (feed.get("marketOHLC") or {}).get("ohlc", []):
        if bar.get("interval") == "1d":
            return {key: _number(bar.get(key)) for key in ("open", "high", "low")}
    return {}


def normalize(key: str, target: Target, feed: dict) -> dict | None:
    """Turn one decoded feed (full or LTPC mode) into the payload for the browser.

    Args:
        key: The Upstox instrument key.
        target: What the key is (company or index).
        feed: One value of `FeedResponse.feeds`, as `MessageToDict` returns it.

    Returns:
        The payload, or None when the feed has no last trade price (for example an empty
        initial frame).

    Raises:
        pydantic.ValidationError: If the last trade fields are invalid (for example a zero price).
    """
    full = feed.get("fullFeed") or {}
    block = full.get("marketFF") or full.get("indexFF") or {}
    raw = block.get("ltpc") or feed.get("ltpc")
    if not raw or "ltp" not in raw:
        return None
    ltpc = Ltpc.model_validate(raw)
    previous = ltpc.cp if ltpc.cp else None
    payload = {
        "key": key,
        "kind": target.kind,
        "name": target.name,
        "symbol": target.symbol,
        "company_id": target.company_id,
        "ltp": ltpc.ltp,
        "as_of": _iso(ltpc.ltt),
        "previous_close": previous,
        "change": ltpc.ltp - previous if previous else None,
        "change_pct": (ltpc.ltp / previous - 1) * 100 if previous else None,
        "open": None,
        "high": None,
        "low": None,
        **_day_ohlc(block),
    }
    if target.kind == LiveSnapshot.Kind.EQUITY:
        depth = [
            {
                "bid_price": _number(level.get("bidP")),
                "bid_qty": int(level.get("bidQ") or 0),
                "ask_price": _number(level.get("askP")),
                "ask_qty": int(level.get("askQ") or 0),
            }
            for level in (block.get("marketLevel") or {}).get("bidAskQuote", [])[:DEPTH_LEVELS]
        ]
        volume = block.get("vtt")
        payload |= {
            "volume": int(volume) if volume is not None else None,
            "average_price": _number(block.get("atp")),
            "total_buy_qty": _number(block.get("tbq")),
            "total_sell_qty": _number(block.get("tsq")),
            "depth": depth,
        }
    return payload


def normalize_status(info: dict) -> dict:
    """Return the exchange segment states of a `market_info` frame (for example NSE_EQ: open).

    Args:
        info: The `marketInfo` block of the frame.

    Returns:
        The status payload stored and sent to browsers.
    """
    segments = info.get("segmentStatus") or {}
    return {
        "key": STATUS_KEY,
        "kind": LiveSnapshot.Kind.STATUS,
        "segments": {str(name): str(state) for name, state in segments.items()},
        "as_of": timezone.now().isoformat(),
    }


async def _send(messages: list[tuple[str, dict]]) -> None:
    """Send each (group, message) pair through the channel layer.

    Args:
        messages: Pairs of a group name and a channel-layer message.
    """
    layer = get_channel_layer()
    if layer is None:
        return
    for group, message in messages:
        await layer.group_send(group, message)


def broadcast(payloads: Iterable[dict], loop: asyncio.AbstractEventLoop | None = None) -> None:
    """Send the payloads to the groups of their company, or to the index group.

    Quotes of one group go in one `quote.update` message. The market status goes to the index
    group as a `market.status` message.

    Args:
        payloads: Normalized payloads (`normalize` or `normalize_status`).
        loop: An event loop owned by the calling thread. The Redis layer keeps one connection
            pool for each loop, so a long-running caller passes the same loop each time to reuse
            its connection. Without it, each call runs on a new loop and a new connection.

    Raises:
        Exception: Any error of the channel layer (for example Redis is down). The caller logs it.
    """
    quotes: dict[str, list[dict]] = defaultdict(list)
    messages: list[tuple[str, dict]] = []
    for payload in payloads:
        if payload["kind"] == LiveSnapshot.Kind.STATUS:
            messages.append((INDEX_GROUP, {"type": "market.status", "status": payload}))
        elif payload.get("company_id"):
            quotes[company_group(payload["company_id"])].append(payload)
        else:
            quotes[INDEX_GROUP].append(payload)
    messages += [
        (group, {"type": "quote.update", "quotes": items}) for group, items in quotes.items()
    ]
    if not messages:
        return
    if loop is None:
        async_to_sync(_send)(messages)
    else:
        loop.run_until_complete(_send(messages))


def store(payloads: Iterable[dict]) -> None:
    """Upsert the newest payloads in `LiveSnapshot` without model signals.

    Args:
        payloads: Normalized quote or status payloads with a `key`.
    """
    now = timezone.now()
    rows = [
        LiveSnapshot(
            key=payload["key"],
            kind=payload["kind"],
            company_id=payload.get("company_id"),
            payload=payload,
            updated_at=now,
        )
        for payload in payloads
    ]
    if rows:
        LiveSnapshot.objects.bulk_create(
            rows,
            update_conflicts=True,
            unique_fields=["key"],
            update_fields=["kind", "company", "payload", "updated_at"],
        )


def snapshot(*, companies: Iterable[int] = (), indices: bool = False) -> dict:
    """Read the saved newest payloads for a new subscriber.

    Args:
        companies: Company ids whose quotes to include.
        indices: If true, include all index quotes and the market status.

    Returns:
        A dict with `quotes` (a list of payloads) and, with `indices`, `status` (or None).
    """
    rows = LiveSnapshot.objects.filter(company_id__in=list(companies))
    if indices:
        rows = rows | LiveSnapshot.objects.filter(
            kind__in=[LiveSnapshot.Kind.INDEX, LiveSnapshot.Kind.STATUS]
        )
    result: dict = {"quotes": []}
    if indices:
        result["status"] = None
    for row in rows.order_by("pk"):
        if row.kind == LiveSnapshot.Kind.STATUS:
            result["status"] = row.payload
        else:
            result["quotes"].append(row.payload)
    return result
