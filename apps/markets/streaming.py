"""TLS-verified V3 feed decoding, validation, live broadcasts and rate-limited persistence.

`FeedWriter` receives the binary full-mode frames. It keeps the newest payload of each instrument
and a separate flusher thread publishes them about once a second (`live.py`): to `LiveSnapshot`
and to the Channels groups that browser WebSockets join. A company observation is also saved as a
`CompanyQuote` at most once in 5 seconds. All writes are bulk writes, so no model signal fires.
"""

import asyncio
import json
import logging
import threading
import time
from collections.abc import Iterable, Mapping
from datetime import datetime
from urllib.parse import urlsplit

import websocket
from django.db import DatabaseError, close_old_connections, connections
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError
from google.protobuf.message_factory import GetMessageClass
from pydantic import ValidationError
from upstox_client.feeder.proto import MarketDataFeedV3_pb2

from apps.companies.models import Company, CompanyQuote

from . import live
from .upstox import record_error
from .upstox_client import UpstoxClient, UpstoxError

logger = logging.getLogger(__name__)
SAVE_INTERVAL = 5
PUBLISH_INTERVAL = 1.0
SUBSCRIBE_CHUNK = 500
FEED_RESPONSE = GetMessageClass(
    MarketDataFeedV3_pb2.DESCRIPTOR.message_types_by_name["FeedResponse"]
)


def authorized_uri() -> str:
    """Ask Upstox for a new address of the market-data feed.

    The function runs at each connect, because the address is short-lived. It accepts only a
    `wss://` address on a host that ends with `.upstox.com`.

    Returns:
        The authorized WebSocket address. It can contain a one-time credential, so never log it.

    Raises:
        UpstoxError: If the request fails or the answer has no valid address.
    """
    with UpstoxClient() as client:
        response = client.get("v3/feed/market-data-feed/authorize")
    data = response.data
    uri = data.get("authorized_redirect_uri") if isinstance(data, dict) else None
    if not isinstance(uri, str):
        raise UpstoxError("Upstox returned an invalid streaming endpoint.")
    parts = urlsplit(uri)
    if parts.scheme != "wss" or not parts.hostname or not parts.hostname.endswith(".upstox.com"):
        raise UpstoxError("Upstox returned an invalid streaming endpoint.")
    return uri


def index_name(key: str) -> str:
    """Return the display name of an index key, for example `Nifty 50` for `NSE_INDEX|Nifty 50`.

    Args:
        key: The Upstox instrument key.

    Returns:
        The name after the `|`, or the key.
    """
    return key.partition("|")[2] or key


class FeedWriter:
    """Keep the newest tick per instrument; broadcast and persist at bounded rates."""

    def __init__(self, companies: Mapping[str, Company], indices: Iterable[str] = ()):
        """Start with the instruments to follow and nothing published.

        Args:
            companies: A dict from the Upstox instrument key to the `Company`.
            indices: Upstox index instrument keys, for example `NSE_INDEX|Nifty 50`.
        """
        self.companies = dict(companies)
        self.targets: dict[str, live.Target] = {
            key: live.Target("index", index_name(key)) for key in indices
        }
        self.targets |= {
            key: live.Target("equity", company.name, company.pk, company.symbol)
            for key, company in self.companies.items()
        }
        self.saved_at: dict[str, float] = {}
        self.pending: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.thread: threading.Thread | None = None
        self.invalid = False
        self.received = False
        self.broadcast_failing = False

    def on_open(self, ws):
        """Subscribe to all instruments in `full` mode, in the binary V3 format.

        Args:
            ws: The open WebSocket.
        """
        keys = list(self.targets)
        logger.info("Upstox V3 connected; subscribing to %d instruments.", len(keys))
        for start in range(0, len(keys), SUBSCRIBE_CHUNK):
            ws.send(
                json.dumps(
                    {
                        "guid": f"kashengine-{start}",
                        "method": "sub",
                        "data": {
                            "instrumentKeys": keys[start : start + SUBSCRIBE_CHUNK],
                            "mode": "full",
                        },
                    }
                ).encode(),
                opcode=websocket.ABNF.OPCODE_BINARY,
            )

    def save(self, key: str, payload: dict) -> None:
        """Save a company payload as a `CompanyQuote`, at most one time in 5 seconds per key.

        The saved time is the last-trade time from Upstox, not the time of receipt. A repeated
        tick with the same time makes no new row. A saved quote clears an old `quotes` error of the
        company.

        Args:
            key: The Upstox instrument key of a company.
            payload: The normalized payload (`live.normalize`).
        """
        now = time.monotonic()
        if now - self.saved_at.get(key, -SAVE_INTERVAL) < SAVE_INTERVAL:
            return
        company = self.companies[key]
        as_of = datetime.fromisoformat(payload["as_of"])
        exists = CompanyQuote.objects.filter(company=company, as_of=as_of).exists()
        CompanyQuote.objects.bulk_create(
            [
                CompanyQuote(
                    company=company,
                    as_of=as_of,
                    instrument_key=key,
                    price=payload["ltp"],
                    previous_close=payload["previous_close"],
                    volume=payload.get("volume"),
                    mode="stream",
                )
            ],
            ignore_conflicts=True,
        )
        if not exists:
            quote = CompanyQuote.objects.filter(company=company, as_of=as_of).first()
            if quote is not None:
                from apps.companies.alerts import evaluate_price_alerts  # noqa: PLC0415

                evaluate_price_alerts(quote)
        if company.upstox_errors.get("quotes"):
            record_error(company, "quotes")
        self.saved_at[key] = now

    def on_message(self, ws, message):
        """Decode one feed message, queue its payloads and save company quotes.

        A message that is not binary, cannot be decoded or is not valid stops the connection and
        sets `invalid`. The code does not guess a quote.

        Args:
            ws: The WebSocket.
            message: The message from Upstox. It must be bytes (protobuf).
        """
        if not isinstance(message, bytes):
            logger.warning("Upstox stream returned a non-protobuf message.")
            self.invalid = True
            ws.close()
            return
        try:
            payload = MessageToDict(FEED_RESPONSE.FromString(message))
            close_old_connections()
            updates = {}
            if payload.get("type") == "market_info" and "marketInfo" in payload:
                updates[live.STATUS_KEY] = live.normalize_status(payload["marketInfo"])
            for key, feed in payload.get("feeds", {}).items():
                target = self.targets.get(key)
                normalized = target and live.normalize(key, target, feed)
                if normalized:
                    updates[key] = normalized
                    if key in self.companies:
                        self.save(key, normalized)
            if updates:
                self.received = True
                with self.lock:
                    self.pending |= updates
        except (DecodeError, ValidationError, UpstoxError, ValueError, OverflowError):
            logger.exception("Invalid Upstox streaming payload; stopping the connection.")
            self.invalid = True
            ws.close()

    def publish(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Store and broadcast the queued payloads. Errors are logged; the stream goes on.

        Args:
            loop: The event loop of the flusher thread, reused so the Redis connection stays open.
        """
        with self.lock:
            pending, self.pending = self.pending, {}
        if not pending:
            return
        try:
            live.store(pending.values())
        except DatabaseError:
            logger.exception("Could not save live Upstox snapshots.")
        try:
            live.broadcast(pending.values(), loop)
        except Exception:  # The channel layer (Redis) can raise many transport errors.
            if not self.broadcast_failing:
                logger.exception("Could not broadcast live Upstox quotes; check CHANNEL_LAYERS.")
            self.broadcast_failing = True
        else:
            if self.broadcast_failing:
                logger.info("Live Upstox broadcasts recovered.")
            self.broadcast_failing = False

    def start(self) -> None:
        """Start the flusher thread that calls `publish` each `PUBLISH_INTERVAL` seconds."""

        def run():
            """Publish pending ticks each interval until the writer stops.

            One event loop serves the whole thread, so the channel layer keeps one Redis
            connection instead of opening a new one each second.
            """
            loop = asyncio.new_event_loop()
            try:
                while not self.stopped.wait(PUBLISH_INTERVAL):
                    close_old_connections()
                    self.publish(loop)
                self.publish(loop)
            finally:
                loop.close()  # channels-redis closes its pool for this loop here.
                connections.close_all()  # The connections of this thread end with it.

        self.stopped.clear()
        self.thread = threading.Thread(target=run, name="upstox-publisher", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        """Stop the flusher thread after one last publish."""
        self.stopped.set()
        if self.thread is not None:
            self.thread.join(timeout=10)
            self.thread = None

    def on_error(self, ws, _error):
        """Log a short fixed text and close the connection.

        The method ignores the error text, because it can hold the signed address or a header.

        Args:
            ws: The WebSocket.
            _error: The error from the library. It is not logged.
        """
        logger.warning("Upstox stream failed. Check token, entitlement and connectivity.")
        ws.close()
