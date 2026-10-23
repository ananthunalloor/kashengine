"""TLS-verified V3 feed decoding, validation and rate-limited database persistence."""

import json
import logging
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit

import websocket
from django.db import close_old_connections
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError
from google.protobuf.message_factory import GetMessageClass
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from upstox_client.feeder.proto import MarketDataFeedV3_pb2

from apps.companies.models import Company, CompanyQuote

from .upstox import record_error
from .upstox_client import UpstoxClient, UpstoxError

logger = logging.getLogger(__name__)
SAVE_INTERVAL = 5
FEED_RESPONSE = GetMessageClass(
    MarketDataFeedV3_pb2.DESCRIPTOR.message_types_by_name["FeedResponse"]
)


class Tick(BaseModel):
    """Validated LTPC fields from the documented V3 protobuf message."""

    model_config = ConfigDict(allow_inf_nan=False)
    ltp: float = Field(gt=0)
    ltt: int = Field(gt=0)
    cp: float | None = None


def authorized_uri() -> str:
    """Refresh authorization on every reconnect and reject non-Upstox/non-TLS destinations."""
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


class FeedWriter:
    """Keep bounded observations rather than writing every exchange tick."""

    def __init__(self, companies: dict[str, Company]):
        self.companies = companies
        self.saved_at: dict[str, float] = {}
        self.invalid = False

    def on_open(self, ws):
        """Subscribe using the binary V3 request format."""
        logger.info("Upstox V3 connected; subscribing to %d instruments.", len(self.companies))
        ws.send(
            json.dumps(
                {
                    "guid": "kashengine",
                    "method": "sub",
                    "data": {"instrumentKeys": list(self.companies), "mode": "ltpc"},
                }
            ).encode(),
            opcode=websocket.ABNF.OPCODE_BINARY,
        )

    def save(self, key: str, raw: dict) -> None:
        """Validate exchange data and preserve provider last-trade time, not receive time."""
        now = time.monotonic()
        if now - self.saved_at.get(key, -SAVE_INTERVAL) < SAVE_INTERVAL:
            return
        tick = Tick.model_validate(raw)
        company = self.companies[key]
        CompanyQuote.objects.get_or_create(
            company=company,
            as_of=datetime.fromtimestamp(tick.ltt / 1000, UTC),
            defaults={
                "instrument_key": key,
                "price": tick.ltp,
                "previous_close": tick.cp if tick.cp and tick.cp > 0 else None,
                "volume": None,
                "mode": "stream",
            },
        )
        if company.upstox_errors.get("quotes"):
            record_error(company, "quotes")
        self.saved_at[key] = now

    def on_message(self, ws, message):
        """Stop on malformed data rather than accepting a partial/guessed quote."""
        if not isinstance(message, bytes):
            logger.warning("Upstox stream returned a non-protobuf message.")
            self.invalid = True
            ws.close()
            return
        try:
            payload = MessageToDict(FEED_RESPONSE.FromString(message))
            close_old_connections()
            for key, feed in payload.get("feeds", {}).items():
                if key in self.companies and "ltpc" in feed:
                    self.save(key, feed["ltpc"])
        except (DecodeError, ValidationError, UpstoxError, ValueError, OverflowError):
            logger.exception("Invalid Upstox streaming payload; stopping the connection.")
            self.invalid = True
            ws.close()

    def on_error(self, ws, _error):
        """Never log SDK errors containing signed URLs or authorization headers."""
        logger.warning("Upstox stream failed. Check token, entitlement and connectivity.")
        ws.close()
