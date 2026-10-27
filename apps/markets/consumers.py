"""Browser WebSocket that relays live Upstox quotes from the stream worker.

Path: `/ws/live/quotes/` (served by the ASGI `realtime` service). The browser must have a signed-in,
verified session with an active subscription and the `markets` feature. On connect it receives the
index quotes and market status. It may then send `{"type": "subscribe", "companies": [ids]}` to
follow up to `MAX_COMPANIES` companies. The server sends:

- `{"type": "snapshot", "quotes": [...], "status": {...}}` with the saved newest values,
- `{"type": "quotes", "quotes": [...]}` with changes (about once a second per instrument),
- `{"type": "status", "status": {...}}` when an exchange segment changes state,
- `{"type": "error", "detail": "..."}` for an invalid client message.

Close codes: 4401 not signed in (or signed out later), 4403 not allowed.
"""

import asyncio
from importlib import import_module
from types import SimpleNamespace

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.contrib import auth

from apps.access.rules import Access
from apps.companies.models import Company

from . import live

MAX_COMPANIES = 25
REVALIDATE_SECONDS = 60
UNAUTHENTICATED = 4401
FORBIDDEN = 4403


def check(user) -> int | None:
    """Return None if the user may receive live quotes, else the WebSocket close code.

    Args:
        user: The signed-in user of the socket, or an anonymous user.

    Returns:
        None when access is allowed, else 4401 (signed out) or 4403 (no Markets access).
    """
    if not user.is_authenticated or not user.is_active:
        return UNAUTHENTICATED
    access = Access(user)
    if not access.email_verified or not access.subscription_ok or not access.can("markets"):
        return FORBIDDEN
    return None


def session_user(session_key: str | None):
    """Load the user of a session again, so a sign-out or password change ends the socket.

    Args:
        session_key: The session key the socket connected with.

    Returns:
        The current user of that session, or an anonymous user.
    """
    store = import_module(settings.SESSION_ENGINE).SessionStore(session_key)
    return auth.get_user(SimpleNamespace(session=store))  # ty: ignore[invalid-argument-type]


def mapped_ids(ids: list[int]) -> list[int]:
    """Keep the ids of saved companies that have an Upstox instrument key.

    Args:
        ids: Company ids sent by the browser.

    Returns:
        The ids that the stream worker can have live quotes for.
    """
    return list(
        Company.objects.filter(pk__in=ids)
        .exclude(upstox_instrument_key="")
        .values_list("pk", flat=True)
    )


class LiveQuotesConsumer(AsyncJsonWebsocketConsumer):
    """One browser connection: the index group plus the groups of the requested companies."""

    async def connect(self):
        """Accept, then check access; close with 4401/4403 so the client can tell why."""
        self.companies: set[int] = set()
        self.watchdog: asyncio.Task | None = None
        await self.accept()
        code = await database_sync_to_async(check)(self.scope["user"])
        if code is not None:
            await self.close(code=code)
            return
        await self.channel_layer.group_add(live.INDEX_GROUP, self.channel_name)
        first = await database_sync_to_async(live.snapshot)(indices=True)
        await self.send_json({"type": "snapshot", **first})
        self.watchdog = asyncio.create_task(self.revalidate())

    async def disconnect(self, code):
        """Leave every group and stop the access watchdog.

        Args:
            code: The WebSocket close code.
        """
        if getattr(self, "watchdog", None):
            self.watchdog.cancel()
        await self.channel_layer.group_discard(live.INDEX_GROUP, self.channel_name)
        for company_id in getattr(self, "companies", set()):
            await self.channel_layer.group_discard(
                live.company_group(company_id), self.channel_name
            )

    async def revalidate(self):
        """Check the session and access each minute; close the socket when they end."""
        session = self.scope.get("session")
        key = getattr(session, "session_key", None)
        while True:
            await asyncio.sleep(REVALIDATE_SECONDS)
            user = await database_sync_to_async(session_user)(key)
            code = await database_sync_to_async(check)(user)
            if code is None and user.pk != self.scope["user"].pk:
                code = UNAUTHENTICATED
            if code is not None:
                await self.close(code=code)
                return

    async def receive_json(self, content, **kwargs):
        """Handle `subscribe`: replace the followed companies and send their snapshot.

        Args:
            content: The decoded JSON message.
            **kwargs: Unused extra arguments from Channels.
        """
        companies = content.get("companies") if isinstance(content, dict) else None
        if (
            not isinstance(content, dict)
            or content.get("type") != "subscribe"
            or not isinstance(companies, list)
            or len(companies) > MAX_COMPANIES
            or not all(type(item) is int and item > 0 for item in companies)
        ):
            await self.send_json(
                {
                    "type": "error",
                    "detail": f"Send a subscribe message with up to {MAX_COMPANIES} company ids.",
                }
            )
            return
        wanted = set(await database_sync_to_async(mapped_ids)(companies))
        for company_id in self.companies - wanted:
            await self.channel_layer.group_discard(
                live.company_group(company_id), self.channel_name
            )
        for company_id in wanted - self.companies:
            await self.channel_layer.group_add(live.company_group(company_id), self.channel_name)
        self.companies = wanted
        first = await database_sync_to_async(live.snapshot)(companies=wanted)
        await self.send_json({"type": "snapshot", **first})

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        """Reject binary or unreadable frames with an error message instead of a crash.

        Args:
            text_data: A text frame, if one was sent.
            bytes_data: A binary frame, if one was sent.
            **kwargs: Unused extra arguments from Channels.
        """
        if text_data is None:
            await self.send_json({"type": "error", "detail": "Send JSON text frames."})
            return
        try:
            content = await self.decode_json(text_data)
        except ValueError:
            await self.send_json({"type": "error", "detail": "Send valid JSON."})
            return
        await self.receive_json(content, **kwargs)

    async def quote_update(self, event):
        """Relay quotes from the stream worker.

        Args:
            event: The `quote.update` group message with a `quotes` list.
        """
        await self.send_json({"type": "quotes", "quotes": event["quotes"]})

    async def market_status(self, event):
        """Relay a market status change from the stream worker.

        Args:
            event: The `market.status` group message with a `status` dict.
        """
        await self.send_json({"type": "status", "status": event["status"]})
