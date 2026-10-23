"""Authenticated, read-only Upstox REST access with bounded pagination and safe errors."""

from collections.abc import Iterator
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from apps.siteconfig import conf


class UpstoxError(Exception):
    """A provider, authentication, transport, or response-contract failure."""


class Page(BaseModel):
    """The pagination fields shared by news and IPO responses."""

    total_pages: int


class Metadata(BaseModel):
    """Provider pagination envelope."""

    page: Page


class Envelope(BaseModel):
    """Only successful, explicitly data-bearing responses are usable."""

    model_config = ConfigDict(allow_inf_nan=False)
    status: Literal["success"]
    data: dict[str, JsonValue] | list[JsonValue]
    metadata: Metadata | None = None
    meta_data: Metadata | None = None


class UpstoxClient:
    """Read-only API client; neither credentials nor provider error bodies enter logs."""

    def __init__(self, client: httpx.Client | None = None):
        if not conf.UPSTOX_ENABLED:
            raise UpstoxError("Upstox is disabled.")
        if not conf.UPSTOX_ACCESS_TOKEN:
            raise UpstoxError("Configure an Upstox access token in Ops settings.")
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)
        self.owned = client is None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.owned:
            self.client.close()

    def get(self, path: str, params: dict | None = None) -> Envelope:
        """Validate the envelope and report failures without logging request headers."""
        try:
            response = self.client.get(
                f"https://api.upstox.com/{path}",
                params=params,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {conf.UPSTOX_ACCESS_TOKEN}",
                },
            )
        except httpx.HTTPError:
            raise UpstoxError(f"Upstox {path}: network request failed.") from None
        if response.status_code != httpx.codes.OK:
            raise UpstoxError(f"Upstox {path}: HTTP {response.status_code}.")
        try:
            return Envelope.model_validate_json(response.content)
        except ValidationError:
            raise UpstoxError(f"Upstox {path}: invalid or unsuccessful response.") from None

    def pages(self, path: str, params: dict) -> Iterator[Envelope]:
        """Visit every page; missing or excessive pagination fails rather than truncating."""
        for number in range(1, 101):
            response = self.get(path, {**params, "page_number": number})
            metadata = response.metadata or response.meta_data
            if metadata is None or metadata.page.total_pages < 0:
                raise UpstoxError(f"Upstox {path}: invalid pagination.")
            yield response
            if number >= metadata.page.total_pages:
                return
        raise UpstoxError(f"Upstox {path}: pagination exceeds 100 pages.")
