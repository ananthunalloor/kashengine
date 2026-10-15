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

Callers: the Celery task `markets.predict`, the command `predict_market` and the report builder
call `make_prediction`. The module reads `NewsArticle` rows (the scores come from the news app),
`IndexQuote` rows, the instruments in `instruments.py` and the site settings
`PREDICTION_NEWS_WEIGHT`, `PREDICTION_THRESHOLD` and `PREDICTION_MIN_ARTICLES`.
`evaluation.py` imports the `UP`, `DOWN` and `FLAT` values.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from apps.news.models import NewsArticle
from apps.siteconfig import conf

from .instruments import global_cues, total_cue_weight
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
    """The news score and the number of articles behind it.

    Attributes:
        score: The relevance-weighted average sentiment, from -1 to 1. `None` when there are no
            usable articles.
        articles: The number of articles that the score uses.
    """

    score: float | None  # None when there are no scored articles.
    articles: int


def news_window_start(target_day: date) -> datetime:
    """Return the start of the news window for a target day.

    The window starts at the market close of the trading day before the target day. The news
    that came after that close is the news that the market has not yet priced in.

    Args:
        target_day: The trading day that we predict.

    Returns:
        A timezone-aware datetime (IST) of that close.
    """
    return session_close(previous_trading_day(target_day))


def news_signal(since: datetime) -> NewsSignal:
    """Return the average sentiment of the scored articles since a time.

    Each article counts as much as its relevance. The function uses only articles that have a
    score (`scored_at` and `sentiment_score` are set) and a relevance of at least 0.2. The time
    of an article is `published_at`. If it is empty, the function uses `fetched_at`.

    Args:
        since: The start of the window. It must be timezone-aware.

    Returns:
        A `NewsSignal`. If no article matches, or if the total relevance is zero, the score is
        `None` and the number of articles is 0.
    """
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
    """The latest reading of one global cue.

    Attributes:
        symbol: The Yahoo Finance symbol of the cue.
        name: The display name of the cue.
        change_pct: The change of the last close, in percent.
        as_of: The day of that close.
        weight: The weight of the cue, with its sign.
        signal: The change divided by the scale of the cue, cut to the range -1 to 1.
    """

    symbol: str
    name: str
    change_pct: float
    as_of: date
    weight: float  # With a sign. A minus sign means that a rise is bad for India.
    signal: float  # The change divided by the scale, cut to -1..1.


def cue_signal(change_pct: float, scale: float) -> float:
    """Return the change divided by the scale, cut to the range -1 to 1.

    Args:
        change_pct: The change of the cue, in percent.
        scale: The move in percent that counts as a full signal. It must not be zero.

    Returns:
        A number from -1.0 to 1.0. A change that is bigger than the scale gives 1.0 or -1.0.
    """
    return max(-1.0, min(1.0, change_pct / scale))


def read_cues(target_day: date) -> list[CueReading]:
    """Read the latest change of each enabled global cue.

    For each cue, the function takes the newest quote that has a change, on `target_day` or
    earlier, and not older than 4 days (`MAX_CUE_AGE_DAYS`). The 4 days cover a long weekend. A
    cue without such a quote is left out.

    Args:
        target_day: The trading day that we predict.

    Returns:
        A list of `CueReading` values, in the order of `global_cues()`. It is empty when no cue
        has a recent quote.
    """
    oldest = target_day - timedelta(days=MAX_CUE_AGE_DAYS)
    readings = []
    for cue in global_cues():
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
    """Return the weighted average of the cue signals, from -1 to 1.

    Each signal is multiplied by its weight (with its sign). The sum is divided by the sum of the
    absolute weights of the cues that are present.

    Args:
        readings: The cue readings, for example from `read_cues`.

    Returns:
        The score, or `None` if the list is empty.
    """
    if not readings:
        return None
    total_weight = sum(abs(r.weight) for r in readings)
    return sum(r.weight * r.signal for r in readings) / total_weight


@dataclass(frozen=True)
class Outcome:
    """The result of the rule: direction, confidence and the numbers behind them.

    Attributes:
        direction: `UP`, `DOWN` or `FLAT`.
        confidence: A number from 0.05 to 0.9. It is not a probability.
        score: The final score, from -1 to 1.
        news_score: The score of the news part, or `None` when there is no news score.
        global_score: The score of the global part, or `None` when there are no cues.
        coverage: A number from 0 to 1. How much of the wanted data is present.
        notes: Short texts that say what is missing or in conflict. They go to `Prediction.inputs`.
    """

    direction: str
    confidence: float
    score: float
    news_score: float | None
    global_score: float | None
    coverage: float  # From 0 to 1. How much of the data that the rule wants is there.
    notes: list[str] = field(default_factory=list)


def _news_part(news: NewsSignal, news_weight: float, min_articles: int, notes: list[str]) -> float:
    """Return the weight of the news in the score. It is lower when there are few articles.

    The weight is `news_weight` times the share of the wanted articles that we have (at most 1).

    Args:
        news: The news signal.
        news_weight: The full weight of the news, from 0 to 1.
        min_articles: The number of articles that gives the full weight.
        notes: A list that the function appends a text to when the news is missing or thin.

    Returns:
        The weight of the news part. It is 0.0 when there is no news score.

    Side effects:
        Appends to `notes`.
    """
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
    """Return the weight of the global cues in the score. It is lower when cues are missing.

    The weight is `1 - news_weight` times the share of the total cue weight that is present.

    Args:
        g_score: The global score. `None` means that there are no cues.
        readings: The cue readings that are present.
        news_weight: The full weight of the news, from 0 to 1.
        notes: A list that the function appends a text to when cues are missing.

    Returns:
        The weight of the global part. It is 0.0 when `g_score` is `None`.

    Side effects:
        Appends to `notes`. Reads the enabled cues from the database.
    """
    if g_score is None:
        notes.append("No global cues.")
        return 0.0
    cues = global_cues()
    if len(readings) < len(cues):
        notes.append(f"Only {len(readings)} of {len(cues)} global cues are available.")
    used = sum(abs(r.weight) for r in readings)
    return (1 - news_weight) * used / total_cue_weight(cues)


def _direction(score: float, threshold: float) -> str:
    """Return UP, DOWN or FLAT for a score.

    Args:
        score: The final score, from -1 to 1.
        threshold: The score that is needed for UP (or minus it for DOWN).

    Returns:
        `UP` when the score is at or above the threshold, `DOWN` when it is at or below minus the
        threshold, and `FLAT` for all other scores.
    """
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
    """Return the confidence before the coverage factor. Lower it when the two scores disagree.

    For FLAT, the value is from 0.30 to 0.50. It is higher when the score is nearer to zero. For
    UP and DOWN, the value is from 0.40 to 0.80. It is higher when the score is stronger. The
    function takes 0.10 off when the news score and the global score have opposite signs and both
    are stronger than 0.1.

    Args:
        direction: `UP`, `DOWN` or `FLAT`.
        score: The final score.
        threshold: The score that is needed for UP or DOWN.
        n_score: The news score, or `None`.
        g_score: The global score, or `None`.
        notes: A list that the function appends a text to when the two scores disagree.

    Returns:
        The base confidence, before `decide` multiplies it by the coverage factor.

    Side effects:
        Appends to `notes`.
    """
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
    """Combine the news and the global cues into a direction and a confidence.

    This is the rule itself. It does not use the database for the news or the quotes, but
    `global_cues` reads the enabled cues. The score is the weighted average of the news score and
    the global score. The weights are lower when data is missing. The confidence is the base
    confidence times `0.7 + 0.3 * coverage`, cut to the range 0.05 to 0.9, and rounded to 2
    decimal places.

    Args:
        news: The news signal.
        readings: The cue readings that are present.
        news_weight: The full weight of the news, from 0 to 1. The rest is for the cues.
        threshold: The score that is needed for UP or DOWN.
        min_articles: The number of articles that gives the news its full weight.

    Returns:
        An `Outcome`. If there is no data at all (coverage is 0), the direction is `FLAT`, the
        confidence is 0.1 and the score is 0.0.
    """
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

    The target day is the next trading day, from today (IST) on. Today counts if it is one. If a
    prediction for the day exists, the function returns it and does not change it, so the report
    stays the same all day. With `force`, the function makes it again, but only until the result
    is known (`evaluated_at` is empty).

    The function reads the news since `news_window_start`, reads the cues, and calls `decide` with
    the site settings. It saves the direction, the confidence, the scores and an `inputs` dict
    (the time, the window start, the cue readings, the coverage, the notes and the settings).

    Args:
        target_day: The day to predict. The default (None) is the next trading day from today
            in IST. The function does not check that the day is a trading day.
        now: The current time. It must be timezone-aware. The default (None) is the current
            time. It goes in `inputs` as `made_at`.
        force: True makes the prediction again when one exists and has no result yet.

    Returns:
        A tuple of the `Prediction` and a flag. The flag is True when the function made and
        saved the prediction in this call. It is False when an existing prediction came back
        without a change.

    Side effects:
        Creates or updates one row in the `Prediction` table. Writes a log line.
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
        "news_weight": conf.PREDICTION_NEWS_WEIGHT,
        "threshold": conf.PREDICTION_THRESHOLD,
        "min_articles": conf.PREDICTION_MIN_ARTICLES,
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
