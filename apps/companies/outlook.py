"""Persist an explainable, deliberately experimental next-session company signal."""

from datetime import timedelta
from statistics import mean

from django.utils import timezone

from apps.markets.trading import latest_completed_day, next_trading_day

from .models import Company, CompanyOutlook

MIN_CLOSES = 21
FLAT_THRESHOLD = 0.15


def save_outlook(company: Company) -> CompanyOutlook | None:
    """Save an experimental outlook for the next session of one company.

    The score mixes 20-session price momentum (weight 0.7) with the average sentiment of the news
    of the last seven days, weighted by relevance (weight 0.3). Without scored news the score is
    the momentum alone. The score is not a probability or a price target.

    The function makes no outlook without 21 completed daily candles that end on the latest
    completed day. A direction is `up` above 0.15, `down` below -0.15, else `flat`.

    Args:
        company: The company, with its Upstox candles and news already saved.

    Returns:
        The new `CompanyOutlook`. The existing outlook if the target day and the inputs are the
        same. None if there are not enough candles.

    Side effects:
        Can create a row in the `CompanyOutlook` table.
    """
    completed = latest_completed_day()
    candles = list(
        company.candles.filter(
            instrument_key=company.upstox_instrument_key, day__lte=completed
        ).order_by("-day")[:MIN_CLOSES]
    )
    if len(candles) < MIN_CLOSES or candles[0].day != completed:
        return None
    latest, oldest = candles[0], candles[-1]
    change = (latest.close / oldest.close - 1) * 100
    momentum = max(-1.0, min(1.0, change / 10))
    cutoff = timezone.now() - timedelta(days=7)
    articles = list(
        company.news_articles.filter(
            published_at__gte=cutoff,
            published_at__lte=timezone.now(),
            sentiment_score__isnull=False,
            relevance__gt=0,
        ).values("id", "sentiment_score", "relevance")
    )
    total = sum(article["relevance"] for article in articles)
    news = (
        sum(article["sentiment_score"] * article["relevance"] for article in articles) / total
        if total
        else None
    )
    score = round(momentum if news is None else 0.7 * momentum + 0.3 * news, 12)
    inputs = {
        "instrument_key": company.upstox_instrument_key,
        "method": "momentum-news-v1",
        "price_as_of": latest.day.isoformat(),
        "close": latest.close,
        "start_day": oldest.day.isoformat(),
        "start_close": oldest.close,
        "return_20_sessions_pct": change,
        "sma_20": mean(candle.close for candle in candles[:20]),
        "news": articles,
        "news_window_start": cutoff.date().isoformat(),
        "momentum_weight": 1.0 if news is None else 0.7,
        "news_weight": 0.0 if news is None else 0.3,
        "flat_threshold": FLAT_THRESHOLD,
    }
    target = next_trading_day(completed + timedelta(days=1))
    previous = company.outlooks.first()
    # A scheduled REST refresh and a stream worker must not create identical evidence.
    if previous and previous.target_date == target and previous.inputs == inputs:
        return previous
    return CompanyOutlook.objects.create(
        company=company,
        target_date=target,
        direction="up" if score > FLAT_THRESHOLD else "down" if score < -FLAT_THRESHOLD else "flat",
        score=score,
        momentum_score=momentum,
        news_score=news,
        inputs=inputs,
    )
