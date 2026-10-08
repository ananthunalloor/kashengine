"""Small helpers for the markets tests."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.markets.models import IndexQuote, Prediction
from apps.news.models import NewsArticle

IST = ZoneInfo("Asia/Kolkata")

# 2026-10-05 is a Monday. 2026-10-10 and 2026-10-11 are the weekend.
MON = date(2026, 10, 5)
TUE = date(2026, 10, 6)
WED = date(2026, 10, 7)
FRI = date(2026, 10, 9)
SAT = date(2026, 10, 10)
SUN = date(2026, 10, 11)
NEXT_MON = date(2026, 10, 12)
TUE_AFTER = date(2026, 10, 13)
PREV_FRI = date(2026, 10, 2)  # The Friday before MON.


def ist(day: date, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)


def quote(symbol: str, day: date, change_pct: float | None, close: float = 100.0, saved_at=None):
    """Save a quote. `saved_at` sets updated_at (auto_now would use the real time)."""
    row = IndexQuote.objects.create(symbol=symbol, day=day, close=close, change_pct=change_pct)
    if saved_at is not None:
        IndexQuote.objects.filter(pk=row.pk).update(updated_at=saved_at)
    return row


def prediction(day: date, direction: str = "up", confidence: float = 0.6, **kwargs) -> Prediction:
    kwargs.setdefault("score", 0.3)
    return Prediction.objects.create(
        target_date=day, direction=direction, confidence=confidence, **kwargs
    )


def article(number: int, score, relevance, published_at=None, fetched_at=None, scored=True):
    """Save a news article with a sentiment score."""
    row = NewsArticle.objects.create(
        source="Test", title=f"Title {number}", url=f"https://t.test/{number}",
        published_at=published_at, sentiment_score=score, relevance=relevance,
        scored_at=timezone.now() if scored else None,
    )  # fmt: skip
    if fetched_at is not None:
        NewsArticle.objects.filter(pk=row.pk).update(fetched_at=fetched_at)
    return row
