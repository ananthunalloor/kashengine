"""Shared HTTP client for news collection."""

import httpx
from django.conf import settings


def make_client() -> httpx.Client:
    """Make an HTTP client with our User-Agent and a timeout."""
    return httpx.Client(
        headers={"User-Agent": settings.NEWS_USER_AGENT},
        timeout=settings.NEWS_REQUEST_TIMEOUT,
        follow_redirects=True,
    )
