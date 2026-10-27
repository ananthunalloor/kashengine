"""Compare the predictions with the real results, and measure the accuracy.

The real result of a day is the change of the Nifty 50 close. A change inside the flat band
(MARKET_FLAT_BAND_PCT, default 0.25%) counts as "flat".

A prediction is checked only when the quote of its day is final. A quote is final when we saved
it after the close of the market (plus a few minutes). A row that we saved in the middle of the
session can hold a price that is not the close, so we wait for the next download.

A prediction is "void" when the market had no session on that day (a holiday): there is no quote
for that day, but there are quotes for later days. Void predictions are not counted in the
accuracy.

Callers: the Celery task `markets.fetch_quotes` and the command `fetch_quotes` call
`evaluate_pending` after each quote download. The web pages, the Ops pages and the command
`prediction_stats` call `accuracy_stats`. The module uses `Prediction` and `IndexQuote` from
`models.py`, the target symbol from `instruments.py` and the close times from `trading.py`.
"""

import logging
import math
from datetime import datetime

from django.utils import timezone

from apps.siteconfig import conf

from .instruments import target_symbol
from .models import IndexQuote, Prediction
from .prediction import DOWN, FLAT, UP
from .trading import final_buffer, session_close, today_ist

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE = 0.6  # A prediction with this confidence or more is a "high confidence" one.
RECENT_RESULTS = 30  # The number of latest results in the "recent" accuracy.
MIN_RESULTS_TO_TRUST = 30  # Fewer results than this is too little to judge the accuracy.


def classify_change(change_pct: float, band: float | None = None) -> str:
    """Return the direction (UP, DOWN or FLAT) for a change in percent.

    A change that is exactly equal to the band, or to minus the band, is FLAT. Only a change
    outside the band is UP or DOWN.

    Args:
        change_pct: The change of the close from the day before, in percent.
        band: The half-width of the flat band, in percent. The default (None) is the site setting
            `MARKET_FLAT_BAND_PCT`. A test can give its own value.

    Returns:
        The `UP`, `DOWN` or `FLAT` text from `prediction.py`.
    """
    band = conf.MARKET_FLAT_BAND_PCT if band is None else band
    if change_pct > band:
        return UP
    if change_pct < -band:
        return DOWN
    return FLAT


def evaluate_pending(now: datetime | None = None) -> dict:
    """Check the predictions that have no result yet. Safe to run many times.

    The function looks at each prediction that has no `evaluated_at` and a target date that is
    today (IST) or earlier. It reads the quote of the target index for that day and puts the
    prediction in one of three states.

    - Evaluated: the quote has a change and its `updated_at` is at or after the close of the
      market plus the final buffer (see `trading.final_buffer`). The function saves the real
      change, the real direction, `correct` and `evaluated_at`.
    - Void: no quote exists for the day, but a quote exists for a later day. The market had no
      session. The function sets only `evaluated_at`, so `correct` stays empty.
    - Waiting: all other cases. The function does not change the prediction. The next run checks
      it again.

    Args:
        now: The current time. It must be timezone-aware. The default (None) is the current
            time. The function also saves it as `evaluated_at`.

    Returns:
        A dict with the keys `evaluated`, `void` and `waiting`. Each value is the number of
        predictions in that state in this run.

    Raises:
        NoTargetError: When no instrument has the kind `target` (raised by `target_symbol`).

    Side effects:
        Updates rows in the `Prediction` table. The function saves each row alone, without a
        transaction around all rows.

    Note:
        A quote that has no `change_pct` never becomes final. The prediction stays in the
        waiting state.
    """
    now = now or timezone.now()
    stats = {"evaluated": 0, "void": 0, "waiting": 0}
    symbol = target_symbol()
    pending = (
        Prediction.objects.filter(evaluated_at__isnull=True, target_date__lte=today_ist(now))
        .exclude(direction="withheld")
        .order_by("target_date")
    )

    for prediction in pending:
        quote = IndexQuote.objects.filter(symbol=symbol, day=prediction.target_date).first()
        final_after = session_close(prediction.target_date) + final_buffer()

        if (
            quote
            and quote.change_pct is not None
            and math.isfinite(quote.change_pct)
            and math.isfinite(quote.close)
            and quote.close > 0
            and now >= final_after
            and final_after <= quote.updated_at <= now
        ):
            actual = classify_change(quote.change_pct, prediction.inputs.get("evaluation_band"))
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
    """Count the predictions in a queryset, and count how many are correct.

    Args:
        queryset: A queryset of `Prediction` rows. The caller filters it to rows with a result.

    Returns:
        A dict with the key `n` (the number of rows) and the key `correct` (the number of rows
        where `correct` is True).
    """
    return {"n": queryset.count(), "correct": queryset.filter(correct=True).count()}


def accuracy_stats() -> dict:
    """Return the accuracy numbers, with a baseline that always guesses the common result.

    Only predictions with a result (`correct` is not empty) count. Void predictions and
    predictions that wait for a result are only counted in `void` and `pending`.

    The baseline is a player that always guesses the direction that happened most often. If two
    directions are equal, the first one in the order up, down, flat wins.

    Returns:
        A dict with these keys.

        - `total`: the number of predictions with a result.
        - `correct`: how many of them are correct.
        - `accuracy`: `correct` divided by `total`, from 0 to 1. `None` when `total` is 0.
        - `by_prediction`: for each direction that we predicted, a dict with `n` and `correct`.
        - `actual_counts`: for each direction, how many times it really happened.
        - `baseline_direction`: the most common real direction. `None` when `total` is 0.
        - `baseline_accuracy`: the share of that direction, from 0 to 1. `None` when `total` is 0.
        - `high_confidence`: a dict with `n` and `correct` for predictions with a confidence of
          0.6 or more.
        - `recent`: a dict with `n` and `correct` for the latest 30 results (by target date).
        - `void`: the number of void predictions.
        - `pending`: the number of predictions that have no `evaluated_at`.
        - `enough_results`: True when `total` is 30 or more.
    """
    results = Prediction.objects.filter(correct__isnull=False).exclude(direction="withheld")
    total = results.count()
    right = results.filter(correct=True).count()

    actual_counts = {
        d.value: results.filter(actual_direction=d).count()
        for d in Prediction.Direction
        if d != Prediction.Direction.WITHHELD
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
            d.value: _count(results.filter(direction=d))
            for d in Prediction.Direction
            if d != Prediction.Direction.WITHHELD
        },
        "actual_counts": actual_counts,
        "baseline_direction": baseline_direction if total else None,
        "baseline_accuracy": baseline_n / total if total else None,
        "high_confidence": _count(results.filter(confidence__gte=HIGH_CONFIDENCE)),
        "recent": {"n": len(recent), "correct": sum(recent)},
        "void": Prediction.objects.filter(evaluated_at__isnull=False, correct__isnull=True)
        .exclude(direction="withheld")
        .count(),
        "pending": Prediction.objects.filter(evaluated_at__isnull=True)
        .exclude(direction="withheld")
        .count(),
        "enough_results": total >= MIN_RESULTS_TO_TRUST,
    }
