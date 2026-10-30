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
        """Check that Upstox is on and has a token, and prepare the HTTP client.

        Args:
            client: An HTTP client. The default is a new client with a 30-second timeout that
                does not follow redirects. Tests give a fake client.

        Raises:
            UpstoxError: If the setting `UPSTOX_ENABLED` is off or the access token is empty.
        """
        if not conf.UPSTOX_ENABLED:
            raise UpstoxError("Upstox is disabled.")
        if not conf.UPSTOX_ACCESS_TOKEN:
            raise UpstoxError("Configure an Upstox access token in Ops settings.")
        self.access_token = conf.UPSTOX_ACCESS_TOKEN
        self.access_token = conf.UPSTOX_ACCESS_TOKEN
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)
        self.owned = client is None

    def __enter__(self):
        """Return the client, so that it works in a `with` block."""
        return self

    def __exit__(self, *args):
        """Close the HTTP client if this object made it.

        Args:
            *args: The exception details of the `with` block. The method ignores them.
        """
        if self.owned:
            self.client.close()

    def get(self, path: str, params: dict | None = None) -> Envelope:
        """Send one `GET` request to the Upstox API and check the answer.

        The access token goes in the `Authorization` header. It never goes in a URL, an error text
        or a log line.

        Args:
            path: The path after `https://api.upstox.com/`, for example `v2/ipos`.
            params: The query parameters, or None.

        Returns:
            The checked `Envelope` (status `success` and a `data` value).

        Raises:
            UpstoxError: If the network fails, the HTTP status is not 200, or the body does not
                match the expected shape.
        """
        try:
            response = self.client.get(
                f"https://api.upstox.com/{path}",
                params=params,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.access_token}",
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
        """Read every page of a paged answer, one request for each page.

        The method stops with an error and never returns a partial list without a warning.

        Args:
            path: The path after `https://api.upstox.com/`.
            params: The query parameters. The method adds `page_number`.

        Yields:
            The checked `Envelope` of each page, from page 1.

        Raises:
            UpstoxError: If a request fails, the answer has no valid page count, or there are more
                than 100 pages.
        """
        for number in range(1, 101):
            response = self.get(path, {**params, "page_number": number})
            metadata = response.metadata or response.meta_data
            if metadata is None or metadata.page.total_pages < 0:
                raise UpstoxError(f"Upstox {path}: invalid pagination.")
            yield response
            if number >= metadata.page.total_pages:
                return
        raise UpstoxError(f"Upstox {path}: pagination exceeds 100 pages.")
