"""Shared HTTP client for news collection."""

import httpx

from apps.siteconfig import conf


def make_client() -> httpx.Client:
    """Make an HTTP client with our User-Agent and a timeout."""
    return httpx.Client(
        headers={"User-Agent": conf.NEWS_USER_AGENT},
        timeout=conf.NEWS_REQUEST_TIMEOUT,
        follow_redirects=True,
    )
