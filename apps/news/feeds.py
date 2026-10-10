"""The shape of one RSS feed. The feeds themselves are in the database (model NewsFeed).

An admin adds, changes, and stops feeds on the Ops pages (Ops > Feeds). A feed that fails is
logged and skipped. It does not stop the other feeds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Feed:
    """One RSS feed of a news source."""

    source: str
    name: str
    url: str
    enabled: bool = True
    pk: int | None = None  # The NewsFeed row, if the feed comes from the database.
