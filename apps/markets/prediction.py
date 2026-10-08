"""The prediction for the next trading day (Nifty 50).

The rule is simple on purpose. It has three steps.

1. News score. The average sentiment of the scored news since the last market close. Each
   article counts as much as its relevance (0 to 1). Articles with a relevance under 0.2 are
   not used. If there are fewer articles than PREDICTION_MIN_ARTICLES, the news counts less.
2. Global score. The change of the global cues (US, Asia, oil, the rupee, the India VIX) at the
   last session, each cut to the range -1 to 1 and weighted (see instruments.py).
3. Score = the weighted average of the two. PREDICTION_NEWS_WEIGHT is the weight of the news.
   Score >= PREDICTION_THRESHOLD is "up". Score <= -PREDICTION_THRESHOLD is "down". Else "flat".

Confidence is not a probability. It is a number from 0 to 1 that grows when the score is far
from the threshold, when the news and the global score agree, and when we have more data. It is
not fitted to data. Do not trust the prediction before `prediction_stats` shows that it beats the
baseline (always guess the most common result) over many days.

Make the prediction in the morning, before the market opens. A later run can see quotes of the
same day.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.news.models import NewsArticle

from .instruments import GLOBAL_CUES, TOTAL_CUE_WEIGHT
from .models import IndexQuote, Prediction
from .trading import next_trading_day, previous_trading_day, session_close, today_ist

logger = logging.getLogger(__name__)

UP = Prediction.Direction.UP.value
DOWN = Prediction.Direction.DOWN.value
FLAT = Prediction.Direction.FLAT.value

MIN_RELEVANCE = 0.2  # Articles with less relevance are not used.
MAX_CUE_AGE_DAYS = 4  # A cue that is older than this is not used. It covers a long weekend.
STRONG_SCORE = 0.6  # A score of this size gives the full strength.
MIN_DISAGREE_SIGNAL = 0.1  # Two scores disagree only when both are stronger than this.


@dataclass(frozen=True)
class NewsSignal:
    """The news score and the number of articles behind it."""

    score: float | None  # None when there are no scored articles.
    articles: int


def news_window_start(target_day: date) -> datetime:
    """The news window starts at the close of the trading day before the target day."""
    return session_close(previous_trading_day(target_day))


def news_signal(since: datetime) -> NewsSignal:
    """The average sentiment of the scored articles since a time, weighted by relevance."""
    rows = (
        NewsArticle.objects.filter(
            scored_at__isnull=False, sentiment_score__isnull=False, relevance__gte=MIN_RELEVANCE
        )
        .filter(Q(published_at__gte=since) | Q(published_at__isnull=True, fetched_at__gte=since))
        .values_list("sentiment_score", "relevance")
    )
    pairs = list(rows)
    total_weight = sum(relevance for _, relevance in pairs)
    if not pairs or total_weight <= 0:
        return NewsSignal(None, 0)
    score = sum(sentiment * relevance for sentiment, relevance in pairs) / total_weight
    return NewsSignal(score, len(pairs))


@dataclass(frozen=True)
class CueReading:
    """The latest reading of one global cue."""

    symbol: str
    name: str
    change_pct: float
    as_of: date
    weight: float  # With a sign. A minus sign means that a rise is bad for India.
    signal: float  # The change divided by the scale, cut to -1..1.


def cue_signal(change_pct: float, scale: float) -> float:
    """Return the change divided by the scale, cut to the range -1 to 1."""
    return max(-1.0, min(1.0, change_pct / scale))


def read_cues(target_day: date) -> list[CueReading]:
    """The latest change of each global cue, for the cues that have a recent quote."""
    oldest = target_day - timedelta(days=MAX_CUE_AGE_DAYS)
    readings = []
    for cue in GLOBAL_CUES:
        quote = (
            IndexQuote.objects.filter(
                symbol=cue.symbol,
                day__lte=target_day,
                day__gte=oldest,
                change_pct__isnull=False,
            )
            .order_by("-day")
            .first()
        )
        if quote is None:
            continue
        readings.append(
            CueReading(
                symbol=cue.symbol,
                name=cue.name,
                change_pct=quote.change_pct,
                as_of=quote.day,
                weight=cue.weight,
                signal=cue_signal(quote.change_pct, cue.scale),
            )
        )
    return readings


def global_score(readings: list[CueReading]) -> float | None:
    """The weighted average of the cues, from -1 to 1. None if there are no cues."""
    if not readings:
        return None
    total_weight = sum(abs(r.weight) for r in readings)
    return sum(r.weight * r.signal for r in readings) / total_weight


@dataclass(frozen=True)
class Outcome:
    """The result of the rule: direction, confidence and the numbers behind them."""

    direction: str
    confidence: float
    score: float
    news_score: float | None
    global_score: float | None
    coverage: float  # From 0 to 1. How much of the data that the rule wants is there.
    notes: list[str] = field(default_factory=list)


def _news_part(news: NewsSignal, news_weight: float, min_articles: int, notes: list[str]) -> float:
    """Return the weight of the news in the score. It is lower when there are few articles."""
    if news.score is None:
        notes.append("No scored news articles.")
        return 0.0
    if news.articles < min_articles:
        notes.append(
            f"Only {news.articles} scored articles (we want {min_articles}). The news counts less."
        )
    return news_weight * min(1.0, news.articles / max(min_articles, 1))


def _global_part(
    g_score: float | None, readings: list[CueReading], news_weight: float, notes: list[str]
) -> float:
    """Return the weight of the global cues in the score. It is lower when cues are missing."""
    if g_score is None:
        notes.append("No global cues.")
        return 0.0
    if len(readings) < len(GLOBAL_CUES):
        notes.append(f"Only {len(readings)} of {len(GLOBAL_CUES)} global cues are available.")
    used = sum(abs(r.weight) for r in readings)
    return (1 - news_weight) * used / TOTAL_CUE_WEIGHT


def _direction(score: float, threshold: float) -> str:
    """Return UP, DOWN or FLAT for a score."""
    if score >= threshold:
        return UP
    if score <= -threshold:
        return DOWN
    return FLAT


def _base_confidence(
    direction: str,
    score: float,
    threshold: float,
    n_score: float | None,
    g_score: float | None,
    notes: list[str],
) -> float:
    """Return the confidence before the coverage factor. Lower it when the two scores disagree."""
    if direction == FLAT:
        # The nearer the score is to zero, the more it looks like a flat day.
        return 0.30 + 0.20 * (1 - abs(score) / threshold)
    base = 0.40 + 0.40 * min(1.0, abs(score) / STRONG_SCORE)
    disagree = (
        n_score is not None
        and g_score is not None
        and n_score * g_score < 0
        and min(abs(n_score), abs(g_score)) > MIN_DISAGREE_SIGNAL
    )
    if disagree:
        base -= 0.10
        notes.append("The news and the global cues point in different directions.")
    return base


def decide(
    news: NewsSignal,
    readings: list[CueReading],
    *,
    news_weight: float,
    threshold: float,
    min_articles: int,
) -> Outcome:
    """Combine the news and the global cues into a direction and a confidence."""
    notes: list[str] = []
    n_score = news.score
    g_score = global_score(readings)

    news_part = _news_part(news, news_weight, min_articles, notes)
    global_part = _global_part(g_score, readings, news_weight, notes)
    coverage = news_part + global_part
    if coverage <= 0:
        return Outcome(FLAT, 0.1, 0.0, n_score, g_score, 0.0, notes)

    score = (news_part * (n_score or 0.0) + global_part * (g_score or 0.0)) / coverage
    direction = _direction(score, threshold)
    base = _base_confidence(direction, score, threshold, n_score, g_score, notes)

    confidence = round(max(0.05, min(0.9, base * (0.7 + 0.3 * coverage))), 2)
    return Outcome(direction, confidence, round(score, 4), n_score, g_score, coverage, notes)


def make_prediction(
    target_day: date | None = None, now: datetime | None = None, force: bool = False
) -> tuple[Prediction, bool]:
    """Make and save the prediction for a trading day. Return (prediction, created).

    - The target day is the next trading day, from today (IST) on. Today counts if it is one.
    - If a prediction for the day exists, it is returned and not changed, so the report stays
      the same all day. force=True makes it again, but only until the result is known.
    """
    now = now or timezone.now()
    target = target_day or next_trading_day(today_ist(now))
    existing = Prediction.objects.filter(target_date=target).first()
    if existing and (existing.evaluated_at or not force):
        return existing, False

    since = news_window_start(target)
    news = news_signal(since)
    readings = read_cues(target)
    config = {
        "news_weight": settings.PREDICTION_NEWS_WEIGHT,
        "threshold": settings.PREDICTION_THRESHOLD,
        "min_articles": settings.PREDICTION_MIN_ARTICLES,
    }
    outcome = decide(news, readings, **config)

    prediction, _ = Prediction.objects.update_or_create(
        target_date=target,
        defaults={
            "direction": outcome.direction,
            "confidence": outcome.confidence,
            "score": outcome.score,
            "news_score": None if outcome.news_score is None else round(outcome.news_score, 4),
            "global_score": None
            if outcome.global_score is None
            else round(outcome.global_score, 4),
            "news_articles": news.articles,
            "inputs": {
                "made_at": now.isoformat(),
                "news_window_start": since.isoformat(),
                "cues": [
                    {
                        "symbol": r.symbol,
                        "name": r.name,
                        "change_pct": round(r.change_pct, 3),
                        "as_of": r.as_of.isoformat(),
                        "weight": r.weight,
                        "signal": round(r.signal, 3),
                    }
                    for r in readings
                ],
                "coverage": round(outcome.coverage, 3),
                "notes": outcome.notes,
                "settings": config,
            },
        },
    )
    logger.info("Prediction for %s: %s (%.2f)", target, prediction.direction, prediction.confidence)
    return prediction, True
