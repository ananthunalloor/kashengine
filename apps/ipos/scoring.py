"""Score the IPOs that have not listed yet. Say which ones are likely to do well.

The rule is simple on purpose. It uses three signals. Each one goes from -1 (bad) to 1 (good).

1. GMP (grey market premium). The GMP in percent of the upper price band. 30% or more is the
   full signal. The GMP is NOT official data. It is a rumour price from a private market. We use
   it only when it is fresh (IPO_METRIC_MAX_AGE_HOURS).
2. Subscription. How many times the issue was bought, on a log scale: 1x is 0, 50x or more is 1,
   under 1x is negative. We use it only when the subscription is final: after the close, or on
   the last day. Early in the issue the number is always low.
3. News. The average sentiment (see apps/news/sentiment.py) of the news of the last
   IPO_NEWS_DAYS that names the IPO. It counts less when there are fewer than 3 articles.

Score = the weighted average of the signals that we have (GMP 0.45, subscription 0.40, news 0.15).
We give a verdict only when we have the GMP or the subscription. The news alone is too thin.
    good     score >= IPO_GOOD_SCORE (default 0.3)
    weak     score <  IPO_WEAK_SCORE (default 0.1)
    mixed    in between
    unknown  no GMP and no subscription that we can use

THE WEIGHTS AND THE LIMITS ARE OUR FIRST GUESS. They are not fitted to data. A GMP of about 9%
gives a score of 0.3, and "did well" means a listing gain of IPO_GOOD_GAIN_PCT (default 10%).
Check the rule with `python manage.py ipo_stats` after some IPOs have listed. IPOs are few:
20 results are the least to say anything.
"""

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.conf import settings
from django.utils import timezone

from apps.companies.matching import normalize_name, normalize_text
from apps.markets.trading import today_ist
from apps.news.models import NewsArticle

from .models import Ipo

logger = logging.getLogger(__name__)

WEIGHTS = {"gmp": 0.45, "subscription": 0.40, "news": 0.15}
GMP_FULL_PCT = 30.0  # A GMP of this size gives the full signal.
SUBSCRIPTION_FULL_TIMES = 50.0
NEWS_FULL_ARTICLES = 3
MIN_NAME_CHARS = 6  # A shorter name gives too many false matches in the news.
MIN_RELEVANCE = 0.2
MIN_RESULTS_TO_TRUST = 20
RECENT_SCORING_DAYS = 30  # We do not score an IPO that opened longer ago than this.

GOOD = Ipo.Verdict.GOOD.value
MIXED = Ipo.Verdict.MIXED.value
WEAK = Ipo.Verdict.WEAK.value
UNKNOWN = Ipo.Verdict.UNKNOWN.value


def _clip(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _is_fresh(stamp: datetime | None, now: datetime) -> bool:
    return stamp is not None and now - stamp <= timedelta(hours=settings.IPO_METRIC_MAX_AGE_HOURS)


# --- The signals ---------------------------------------------------------------------------


def gmp_signal(pct: float) -> float:
    return _clip(pct / GMP_FULL_PCT)


def subscription_signal(times: float) -> float:
    if times <= 0:
        return -1.0
    return _clip(math.log10(times) / math.log10(SUBSCRIPTION_FULL_TIMES))


def subscription_is_final(ipo: Ipo, today: date) -> bool:
    """The number is final after the close, and on the last day (the evening number)."""
    if ipo.close_date is None:
        return False
    return today >= ipo.close_date


def news_signal(ipo: Ipo, now: datetime) -> tuple[float, int] | None:
    """The average news sentiment for the IPO, as (score, articles). None if no article names it."""
    key = normalize_name(ipo.name)
    if len(key) < MIN_NAME_CHARS:
        return None
    since = now - timedelta(days=settings.IPO_NEWS_DAYS)
    pattern = re.compile(rf"(?<![\w&]){re.escape(key)}(?![\w&])", re.IGNORECASE)

    pairs = []
    candidates = NewsArticle.objects.filter(
        scored_at__isnull=False, sentiment_score__isnull=False, relevance__gte=MIN_RELEVANCE
    ).filter(fetched_at__gte=since)
    # The first word is a cheap filter in the database. The pattern checks the whole name.
    first_word = key.split()[0]
    for article in candidates.filter(title__icontains=first_word):
        if pattern.search(normalize_text(f"{article.title} {article.summary}")):
            pairs.append((article.sentiment_score, article.relevance))
    if not pairs:
        return None
    total = sum(weight for _, weight in pairs)
    return sum(score * weight for score, weight in pairs) / total, len(pairs)


# --- The rule ------------------------------------------------------------------------------


@dataclass
class Signal:
    name: str
    value: float  # The raw number: GMP in percent, subscription in times, or news sentiment.
    signal: float  # From -1 to 1.
    strength: float = 1.0  # From 0 to 1. How much we trust it.


@dataclass
class Outcome:
    verdict: str
    score: float | None
    coverage: float
    signals: list[Signal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def decide(signals: list[Signal], notes: list[str], good: float, weak: float) -> Outcome:
    """Combine the signals into a score and a verdict."""
    notes = list(notes)
    if not any(s.name in ("gmp", "subscription") for s in signals):
        notes.append("No usable GMP and no final subscription. We give no verdict.")
        return Outcome(UNKNOWN, None, 0.0, signals, notes)

    used = sum(WEIGHTS[s.name] * s.strength for s in signals)
    score = round(sum(WEIGHTS[s.name] * s.strength * s.signal for s in signals) / used, 4)
    coverage = used / sum(WEIGHTS.values())

    if score >= good:
        verdict = GOOD
    elif score < weak:
        verdict = WEAK
    else:
        verdict = MIXED
    return Outcome(verdict, score, round(coverage, 3), signals, notes)


def score_ipo(ipo: Ipo, now: datetime | None = None) -> Outcome:
    """Work out the score of one IPO. This does not save anything."""
    now = now or timezone.now()
    today = today_ist(now)
    signals: list[Signal] = []
    notes: list[str] = []

    pct = ipo.gmp_pct
    if ipo.gmp is None:
        notes.append("No GMP.")
    elif pct is None:
        notes.append("The GMP is set, but the price band is not. We cannot make a percent.")
    elif not _is_fresh(ipo.gmp_updated_at, now):
        notes.append("The GMP is old. We do not use it.")
    else:
        signals.append(Signal("gmp", round(pct, 2), gmp_signal(pct)))

    if ipo.subscription_times is None:
        notes.append("No subscription number.")
    elif not subscription_is_final(ipo, today):
        notes.append("The subscription is not final before the last day. We do not use it.")
    elif not _is_fresh(ipo.subscription_updated_at, now):
        notes.append("The subscription number is old. We do not use it.")
    else:
        times = float(ipo.subscription_times)
        signals.append(Signal("subscription", times, subscription_signal(times)))

    news = news_signal(ipo, now)
    if news is not None:
        sentiment, articles = news
        signals.append(
            Signal(
                "news",
                round(sentiment, 3),
                _clip(sentiment),
                strength=min(1.0, articles / NEWS_FULL_ARTICLES),
            )
        )

    return decide(signals, notes, settings.IPO_GOOD_SCORE, settings.IPO_WEAK_SCORE)


def _inputs(outcome: Outcome, now: datetime) -> dict:
    return {
        "scored_at": now.isoformat(),
        "coverage": outcome.coverage,
        "signals": [
            {
                "name": s.name,
                "value": s.value,
                "signal": round(s.signal, 3),
                "strength": round(s.strength, 2),
            }
            for s in outcome.signals
        ],
        "notes": outcome.notes,
        "settings": {"good": settings.IPO_GOOD_SCORE, "weak": settings.IPO_WEAK_SCORE},
    }


def scorable_ipos(today: date):
    """The IPOs to score: not listed, and not too old."""
    oldest = today - timedelta(days=RECENT_SCORING_DAYS)
    return (
        Ipo.objects.exclude(status=Ipo.Status.LISTED)
        .filter(listing_gain_pct__isnull=True)
        .exclude(open_date__lt=oldest)
    )


def score_ipos(now: datetime | None = None) -> dict:
    """Score all the IPOs that have not listed yet, and save the scores.

    A listed IPO is not scored again, so its last score stays as it was before the listing.
    Return {"scored": <with a verdict>, "unknown": <no verdict>}.
    """
    now = now or timezone.now()
    stats = {"scored": 0, "unknown": 0}
    for ipo in scorable_ipos(today_ist(now)):
        outcome = score_ipo(ipo, now)
        ipo.score = outcome.score
        ipo.verdict = outcome.verdict
        ipo.scored_at = now
        ipo.score_inputs = _inputs(outcome, now)
        ipo.save(update_fields=["score", "verdict", "scored_at", "score_inputs", "updated_at"])
        stats["unknown" if outcome.verdict == UNKNOWN else "scored"] += 1
    return stats


def likely_good_ipos(today: date | None = None):
    """The IPOs that are open or coming up, with the verdict "good". The best score is first."""
    today = today or today_ist()
    return (
        scorable_ipos(today)
        .filter(verdict=GOOD)
        .exclude(status=Ipo.Status.CLOSED, listing_date__lt=today)
        .order_by("-score", "name")
    )


# --- Results -------------------------------------------------------------------------------


def _did_well(gain: float) -> bool:
    return gain >= settings.IPO_GOOD_GAIN_PCT


def ipo_stats() -> dict:
    """How good were the verdicts? Compare with the baseline: all IPOs, one verdict.

    Only IPOs that had a verdict (not "unknown") before the listing are counted for the verdicts.
    The baseline is the share of all listed IPOs that did well.
    """
    listed = Ipo.objects.filter(listing_gain_pct__isnull=False)
    all_gains = list(listed.values_list("listing_gain_pct", flat=True))
    judged = listed.exclude(verdict__in=[UNKNOWN, ""])

    by_verdict = {}
    for verdict in (GOOD, MIXED, WEAK):
        gains = list(judged.filter(verdict=verdict).values_list("listing_gain_pct", flat=True))
        by_verdict[verdict] = {
            "n": len(gains),
            "did_well": sum(_did_well(g) for g in gains),
            "average_gain": sum(gains) / len(gains) if gains else None,
        }

    judged_total = sum(part["n"] for part in by_verdict.values())
    return {
        "listed": len(all_gains),
        "judged": judged_total,
        "without_verdict": len(all_gains) - judged_total,
        "baseline": sum(_did_well(g) for g in all_gains) / len(all_gains) if all_gains else None,
        "by_verdict": by_verdict,
        "pending": scorable_ipos(today_ist()).count(),
        "enough_results": judged_total >= MIN_RESULTS_TO_TRUST,
    }
