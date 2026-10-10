"""Compare the predictions with the real results, and measure the accuracy.

The real result of a day is the change of the Nifty 50 close. A change inside the flat band
(MARKET_FLAT_BAND_PCT, default 0.25%) counts as "flat".

A prediction is checked only when the quote of its day is final. A quote is final when we saved
it after the close of the market (plus a few minutes). A row that we saved in the middle of the
session can hold a price that is not the close, so we wait for the next download.

A prediction is "void" when the market had no session on that day (a holiday): there is no quote
for that day, but there are quotes for later days. Void predictions are not counted in the
accuracy.
"""

import logging
from datetime import datetime

from django.utils import timezone

from apps.siteconfig import conf

from .instruments import target_symbol
from .models import IndexQuote, Prediction
from .prediction import DOWN, FLAT, UP
from .trading import final_buffer, session_close, today_ist

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE = 0.6
RECENT_RESULTS = 30
MIN_RESULTS_TO_TRUST = 30


def classify_change(change_pct: float, band: float | None = None) -> str:
    """Return UP, DOWN or FLAT for a change in percent. The default band is MARKET_FLAT_BAND_PCT."""
    band = conf.MARKET_FLAT_BAND_PCT if band is None else band
    if change_pct > band:
        return UP
    if change_pct < -band:
        return DOWN
    return FLAT


def evaluate_pending(now: datetime | None = None) -> dict:
    """Check the predictions that have no result yet. Safe to run many times."""
    now = now or timezone.now()
    stats = {"evaluated": 0, "void": 0, "waiting": 0}
    symbol = target_symbol()
    pending = Prediction.objects.filter(
        evaluated_at__isnull=True, target_date__lte=today_ist(now)
    ).order_by("target_date")

    for prediction in pending:
        quote = IndexQuote.objects.filter(symbol=symbol, day=prediction.target_date).first()
        final_after = session_close(prediction.target_date) + final_buffer()

        if quote and quote.change_pct is not None and quote.updated_at >= final_after:
            actual = classify_change(quote.change_pct)
            prediction.actual_change_pct = quote.change_pct
            prediction.actual_direction = actual
            prediction.correct = actual == prediction.direction
            prediction.evaluated_at = now
            prediction.save(
                update_fields=["actual_change_pct", "actual_direction", "correct", "evaluated_at"]
            )
            stats["evaluated"] += 1
        elif (
            quote is None
            and IndexQuote.objects.filter(symbol=symbol, day__gt=prediction.target_date).exists()
        ):
            prediction.evaluated_at = now  # No result. "correct" stays empty.
            prediction.save(update_fields=["evaluated_at"])
            stats["void"] += 1
        else:
            stats["waiting"] += 1
    return stats


def _count(queryset) -> dict:
    """Return the number of rows, and how many of them are correct."""
    return {"n": queryset.count(), "correct": queryset.filter(correct=True).count()}


def accuracy_stats() -> dict:
    """Return the accuracy numbers, with a baseline that always guesses the common result."""
    results = Prediction.objects.filter(correct__isnull=False)
    total = results.count()
    right = results.filter(correct=True).count()

    actual_counts = {
        d.value: results.filter(actual_direction=d).count() for d in Prediction.Direction
    }
    baseline_direction, baseline_n = max(actual_counts.items(), key=lambda item: item[1])
    recent = list(
        results.order_by("-target_date").values_list("correct", flat=True)[:RECENT_RESULTS]
    )

    return {
        "total": total,
        "correct": right,
        "accuracy": right / total if total else None,
        "by_prediction": {
            d.value: _count(results.filter(direction=d)) for d in Prediction.Direction
        },
        "actual_counts": actual_counts,
        "baseline_direction": baseline_direction if total else None,
        "baseline_accuracy": baseline_n / total if total else None,
        "high_confidence": _count(results.filter(confidence__gte=HIGH_CONFIDENCE)),
        "recent": {"n": len(recent), "correct": sum(recent)},
        "void": Prediction.objects.filter(evaluated_at__isnull=False, correct__isnull=True).count(),
        "pending": Prediction.objects.filter(evaluated_at__isnull=True).count(),
        "enough_results": total >= MIN_RESULTS_TO_TRUST,
    }
