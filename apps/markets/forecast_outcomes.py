"""Attach actual, completed outcomes to point-in-time forecast evidence."""

import logging
import math
from datetime import datetime

from apps.companies.models import CompanyCandle
from apps.ipos.models import Ipo

from .models import ForecastSample, IndexQuote
from .trading import final_buffer, session_close, today_ist

logger = logging.getLogger(__name__)


def _actual(sample: ForecastSample, now: datetime) -> float | None:
    """Read only a final, positive price whose session has completed.

    Args:
        sample: The forecast evidence and its outcome reference values.
        now: The latest time allowed for completed outcomes.

    Returns:
        The actual percentage change, or None when no final outcome is available.
    """
    if now < session_close(sample.target_date) + final_buffer():
        return None
    if sample.kind == "ipo":
        ipo = Ipo.objects.filter(pk=sample.entity, listing_date=sample.target_date).first()
        reference = sample.context["issue_price"]
        if ipo and ipo.listing_price is not None and ipo.listing_price > 0 and reference > 0:
            return (float(ipo.listing_price) / reference - 1) * 100
        return None
    if sample.kind == "company":
        candle = CompanyCandle.objects.filter(
            company_id=sample.entity,
            instrument_key=sample.context["instrument_key"],
            day=sample.target_date,
            updated_at__gte=session_close(sample.target_date) + final_buffer(),
            updated_at__lte=now,
        ).first()
        reference = sample.context["reference_close"]
        if candle and reference > 0 and math.isfinite(candle.close) and candle.close > 0:
            return (candle.close / reference - 1) * 100
        return None
    quote = IndexQuote.objects.filter(
        symbol=sample.context["symbol"],
        day=sample.target_date,
        updated_at__gte=session_close(sample.target_date) + final_buffer(),
        updated_at__lte=now,
        close__gt=0,
    ).first()
    return quote.change_pct if quote and math.isfinite(quote.close) else None


def collect_outcomes(now: datetime) -> dict:
    """Label one snapshot per entity/session, without using post-deadline features.

    Args:
        now: The observation time and cutoff for available outcomes.

    Returns:
        Counts of evaluated samples and samples still waiting for outcomes.
    """
    result = {"evaluated": 0, "waiting": 0}
    pending = ForecastSample.objects.filter(
        observed_at__isnull=True,
        target_date__lte=today_ist(now),
        audit__watchdog__status="passed",
    )
    for sample in pending:
        change = _actual(sample, now)
        if change is None or not math.isfinite(change):
            if change is not None:
                logger.warning("Non-finite actual outcome for forecast sample %s", sample.pk)
            result["waiting"] += 1
            continue
        if sample.kind == "ipo":
            label = "good" if change >= sample.context["good_gain"] else "weak"
        else:
            band = sample.context["band"]
            label = "up" if change > band else "down" if change < -band else "flat"
        sample.actual_label = label
        sample.actual_change = change
        sample.observed_at = now
        sample.save(update_fields=["actual_label", "actual_change", "observed_at"])
        result["evaluated"] += 1
    return result
