"""A small client for the Telegram Bot API (https://core.telegram.org/bots/api).

- We send plain text. There is no parse mode, so a character like "<" or "_" can never make
  Telegram refuse the message.
- A message can have 4096 characters at most. A longer text is split at blank lines.
- HTTP 429 ("too many requests") says how many seconds to wait. We wait once, if it is short.
- The URL of every request has the bot token. The token must not appear in a log or in the
  database, so every error text goes through `redact()`.
"""

import logging
import time
from http import HTTPStatus

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org"
MAX_MESSAGE_CHARS = 4096
SAFE_MESSAGE_CHARS = 4000  # A little less than the limit.
MAX_RETRY_WAIT_SECONDS = 30


class TelegramError(Exception):
    """A request to Telegram failed. `retryable` says if a later try can work."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def redact(text: str, token: str) -> str:
    """Remove the bot token from a text."""
    return text.replace(token, "<token>") if token else text


def split_message(text: str, limit: int = SAFE_MESSAGE_CHARS) -> list[str]:
    """Split a text into parts of `limit` characters at most. Split at blank lines if we can."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []

    parts: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        for piece in _fit(block, limit):
            candidate = f"{current}\n\n{piece}" if current else piece
            if len(candidate) <= limit:
                current = candidate
            else:
                parts.append(current)
                current = piece
    if current:
        parts.append(current)
    return parts


def _fit(block: str, limit: int) -> list[str]:
    """Cut one block that is too long, at line breaks, then at spaces, then anywhere."""
    if len(block) <= limit:
        return [block]
    pieces: list[str] = []
    current = ""
    for line in block.split("\n"):
        rest = line
        while len(rest) > limit:  # A very long line.
            cut = rest.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            if current:
                pieces.append(current)
                current = ""
            pieces.append(rest[:cut])
            rest = rest[cut:].lstrip()
        candidate = f"{current}\n{rest}" if current else rest
        if len(candidate) <= limit:
            current = candidate
        else:
            pieces.append(current)
            current = rest
    if current:
        pieces.append(current)
    return pieces


class TelegramClient:
    """Client for the Telegram Bot API. Use it as a context manager to close the HTTP client."""

    def __init__(
        self,
        token: str | None = None,
        client: httpx.Client | None = None,
        timeout: float | None = None,
        sleep=time.sleep,
    ):
        self.token = settings.TELEGRAM_BOT_TOKEN if token is None else token
        if not self.token:
            raise TelegramError("TELEGRAM_BOT_TOKEN is not set.")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout or settings.TELEGRAM_TIMEOUT_SECONDS)
        self._sleep = sleep

    def close(self) -> None:
        """Close the HTTP client, if this object created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def _call(self, method: str, payload: dict | None = None, _retried: bool = False):
        url = f"{API_URL}/bot{self.token}/{method}"
        try:
            response = self._client.post(url, json=payload or {})
        except httpx.HTTPError as exc:
            raise TelegramError(
                redact(f"Cannot reach Telegram: {type(exc).__name__}: {exc}", self.token),
                retryable=True,
            ) from None  # The original error has the URL with the token.

        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code == HTTPStatus.OK and body.get("ok"):
            return body.get("result")

        description = redact(str(body.get("description") or response.text[:200]), self.token)
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            wait = int((body.get("parameters") or {}).get("retry_after") or 5)
            if not _retried and wait <= MAX_RETRY_WAIT_SECONDS:
                logger.warning("Telegram asks us to wait %s seconds.", wait)
                self._sleep(wait)
                return self._call(method, payload, _retried=True)
            raise TelegramError(f"Telegram: too many requests, wait {wait} s", retryable=True)
        if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise TelegramError(
                f"Telegram error {response.status_code}: {description}", retryable=True
            )
        raise TelegramError(f"Telegram error {response.status_code}: {description}")

    def get_me(self) -> dict:
        """Return the bot profile (Telegram getMe)."""
        return self._call("getMe")

    def get_chats(self) -> list[dict]:
        """The chats that sent a message to the bot lately: [{"id", "type", "name"}]."""
        chats: dict[int, dict] = {}
        for update in self._call("getUpdates", {"timeout": 0}) or []:
            message = (
                update.get("message")
                or update.get("channel_post")
                or update.get("edited_message")
                or {}
            )
            chat = message.get("chat")
            if not chat:
                continue
            name = chat.get("title") or " ".join(
                part for part in (chat.get("first_name"), chat.get("last_name")) if part
            )
            chats[chat["id"]] = {
                "id": chat["id"],
                "type": chat.get("type", ""),
                "name": name or chat.get("username", ""),
            }
        return list(chats.values())

    def send_message(self, chat_id: str, text: str) -> int:
        """Send a text. Long texts go in more than one message. Return the number of messages."""
        parts = split_message(text)
        for part in parts:
            self._call(
                "sendMessage",
                {"chat_id": chat_id, "text": part, "disable_web_page_preview": True},
            )
        return len(parts)
