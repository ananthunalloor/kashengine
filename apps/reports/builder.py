"""Build the daily report from the data in the database.

The report has four parts:
1. The Nifty 50 outlook for the day (the prediction, the global cues, the last result, and the
   track record).
2. The news: the strongest good stories and bad stories since the last market close.
3. The IPOs: open now, listing today, coming up, and the ones that are likely to do well.
4. A short warning that this is not advice.

The builder only reads the database. It does not call the LLM and it does not use the network.
So it works also when the LLM server or Yahoo is down. It says what is missing.

The text is plain text, so Telegram can never refuse it because of a bad mark-up, and an email
can use it later. `Report.data` keeps the numbers and the lists for the web page (Phase 8).
"""

import logging
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.ipos.collect import refresh_statuses
from apps.ipos.models import Ipo
from apps.ipos.scoring import likely_good_ipos, score_ipos
from apps.markets.evaluation import MIN_RESULTS_TO_TRUST, accuracy_stats
from apps.markets.models import Prediction
from apps.markets.prediction import make_prediction, news_window_start
from apps.markets.trading import next_trading_day, today_ist
from apps.news.models import NewsArticle

from .models import Report

logger = logging.getLogger(__name__)

ARROWS = {"up": "▲", "down": "▼", "flat": "▬"}
VERDICTS = {
    "good": "likely to do well",
    "mixed": "mixed",
    "weak": "unlikely to do well",
    "unknown": "no verdict (not enough data)",
}
STORY_MIN_SCORE = 0.2  # A story with a smaller score is neutral. We do not show it.
LAST_RESULT_MAX_AGE_DAYS = 7
TITLE_CHARS = 110
REASON_CHARS = 140


def _cut(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _day(value: date) -> str:
    return f"{value:%a} {value.day} {value:%b}"


def _strength(confidence: float) -> str:
    if confidence < 0.4:
        return "weak"
    if confidence < 0.6:
        return "moderate"
    return "strong"


# --- Gathering the data --------------------------------------------------------------------


def gather_prediction(prediction: Prediction) -> dict:
    """The prediction, with the most important global cues."""
    cues = prediction.inputs.get("cues", [])
    # The cues that moved the score most come first.
    cues = sorted(cues, key=lambda c: abs(c["weight"] * c["signal"]), reverse=True)
    return {
        "target_date": prediction.target_date.isoformat(),
        "direction": prediction.direction,
        "confidence": prediction.confidence,
        "score": prediction.score,
        "news_score": prediction.news_score,
        "news_articles": prediction.news_articles,
        "global_score": prediction.global_score,
        "cues": [
            {"name": c["name"], "change_pct": c["change_pct"], "as_of": c["as_of"]}
            for c in cues[:4]
        ],
        "notes": prediction.inputs.get("notes", []),
    }


def gather_last_result(today: date) -> dict | None:
    """The newest prediction that has a result, if it is not too old."""
    last = (
        Prediction.objects.filter(correct__isnull=False)
        .filter(target_date__gte=today - timedelta(days=LAST_RESULT_MAX_AGE_DAYS))
        .order_by("-target_date")
        .first()
    )
    if last is None:
        return None
    return {
        "target_date": last.target_date.isoformat(),
        "direction": last.direction,
        "actual_direction": last.actual_direction,
        "actual_change_pct": last.actual_change_pct,
        "correct": last.correct,
    }


def gather_track_record() -> dict:
    stats = accuracy_stats()
    return {
        "total": stats["total"],
        "correct": stats["correct"],
        "accuracy": stats["accuracy"],
        "baseline_accuracy": stats["baseline_accuracy"],
        "enough_results": stats["enough_results"],
    }


def gather_news(since: datetime, limit: int | None = None) -> dict:
    """The strongest good and bad stories since a time. A story counts by |score| x relevance."""
    limit = settings.REPORT_NEWS_ITEMS if limit is None else limit
    articles = (
        NewsArticle.objects.filter(
            scored_at__isnull=False,
            sentiment_score__isnull=False,
            relevance__gte=settings.REPORT_NEWS_MIN_RELEVANCE,
        )
        .filter(Q(published_at__gte=since) | Q(published_at__isnull=True, fetched_at__gte=since))
        .prefetch_related("companies")
    )
    ranked = sorted(
        articles, key=lambda a: abs(a.sentiment_score) * (a.relevance or 0), reverse=True
    )

    seen: set[str] = set()
    good: list[dict] = []
    bad: list[dict] = []
    for article in ranked:
        key = " ".join(article.title.lower().split())
        if key in seen:
            continue
        seen.add(key)
        item = {
            "title": _cut(article.title, TITLE_CHARS),
            "source": article.source,
            "score": round(article.sentiment_score, 2),
            "reason": _cut(article.sentiment_reason, REASON_CHARS),
            "companies": [c.name for c in list(article.companies.all())[:3]],
            "url": article.url,
        }
        if article.sentiment_score >= STORY_MIN_SCORE and len(good) < limit:
            good.append(item)
        elif article.sentiment_score <= -STORY_MIN_SCORE and len(bad) < limit:
            bad.append(item)
    return {
        "since": since.isoformat(),
        "articles": len(ranked),
        "positive": sum(a.sentiment_score >= STORY_MIN_SCORE for a in ranked),
        "negative": sum(a.sentiment_score <= -STORY_MIN_SCORE for a in ranked),
        "good": good,
        "bad": bad,
    }


def _ipo_item(ipo: Ipo) -> dict:
    gmp_pct = ipo.gmp_pct
    return {
        "name": ipo.name,
        "category": ipo.category,
        "status": ipo.status,
        "open_date": ipo.open_date.isoformat() if ipo.open_date else None,
        "close_date": ipo.close_date.isoformat() if ipo.close_date else None,
        "listing_date": ipo.listing_date.isoformat() if ipo.listing_date else None,
        "price_band_low": float(ipo.price_band_low) if ipo.price_band_low else None,
        "price_band_high": float(ipo.price_band_high) if ipo.price_band_high else None,
        "gmp_pct": None if gmp_pct is None else round(gmp_pct, 1),
        "subscription_times": float(ipo.subscription_times) if ipo.subscription_times else None,
        "verdict": ipo.verdict or "unknown",
        "score": ipo.score,
    }


def gather_ipos(today: date, limit: int | None = None, days_ahead: int | None = None) -> dict:
    """The IPOs that matter today."""
    limit = settings.REPORT_IPO_ITEMS if limit is None else limit
    days_ahead = settings.REPORT_IPO_DAYS_AHEAD if days_ahead is None else days_ahead
    ordering = ("close_date", "name")

    open_now = Ipo.objects.filter(open_date__lte=today, close_date__gte=today).order_by(*ordering)
    listing_today = Ipo.objects.filter(listing_date=today).order_by("name")
    upcoming = Ipo.objects.filter(
        open_date__gt=today, open_date__lte=today + timedelta(days=days_ahead)
    ).order_by("open_date", "name")
    good = likely_good_ipos(today)

    watched = [*open_now, *upcoming]
    return {
        "open_now": [_ipo_item(i) for i in open_now[:limit]],
        "listing_today": [_ipo_item(i) for i in listing_today[:limit]],
        "upcoming": [_ipo_item(i) for i in upcoming[:limit]],
        "likely_good": [_ipo_item(i) for i in good[:limit]],
        "without_verdict": sum(1 for i in watched if (i.verdict or "unknown") == "unknown"),
        "days_ahead": days_ahead,
    }


def gather(day: date, prediction: Prediction) -> dict:
    return {
        "date": day.isoformat(),
        "prediction": gather_prediction(prediction),
        "last_result": gather_last_result(day),
        "track_record": gather_track_record(),
        "news": gather_news(news_window_start(prediction.target_date)),
        "ipos": gather_ipos(day),
    }


# --- The text ------------------------------------------------------------------------------


def _price(item: dict) -> str:
    low, high = item["price_band_low"], item["price_band_high"]
    if high is None:
        return "price band not known"
    if low is None or low == high:
        return f"₹{high:g}"
    return f"₹{low:g}-{high:g}"


def _ipo_line(item: dict, show_verdict: bool = True) -> str:
    parts = [_price(item)]
    if item["status"] == "open" and item["close_date"]:
        parts.append(f"closes {_day(date.fromisoformat(item['close_date']))}")
    elif item["status"] == "upcoming" and item["open_date"]:
        parts.append(f"opens {_day(date.fromisoformat(item['open_date']))}")
    if item["gmp_pct"] is not None:
        parts.append(f"GMP {item['gmp_pct']:+.0f}%")
    if item["subscription_times"] is not None:
        parts.append(f"subscribed {item['subscription_times']:g}x")
    if show_verdict:
        parts.append(VERDICTS[item["verdict"]])
    kind = "SME" if item["category"] == "sme" else "mainboard"
    return f"• {item['name']} ({kind}): " + ", ".join(parts)


def _render_outlook(data: dict) -> list[str]:
    p = data["prediction"]
    target = date.fromisoformat(p["target_date"])
    lines = [
        f"NIFTY 50 OUTLOOK, {_day(target)}",
        f"{ARROWS[p['direction']]} {p['direction'].upper()}: {_strength(p['confidence'])} signal "
        f"(strength {p['confidence']:.2f}, score {p['score']:+.2f}).",
        "The strength is not a probability.",
    ]
    news = (
        "no scored news"
        if p["news_score"] is None
        else f"{p['news_score']:+.2f} from {p['news_articles']} articles"
    )
    glob = "no data" if p["global_score"] is None else f"{p['global_score']:+.2f}"
    lines.append(f"News: {news}. Global markets: {glob}.")
    if p["cues"]:
        lines.append(
            "Cues: " + ", ".join(f"{c['name']} {c['change_pct']:+.1f}%" for c in p["cues"])
        )
    lines.extend(f"Note: {note}" for note in p["notes"])

    last = data["last_result"]
    if last:
        verdict = "right" if last["correct"] else "wrong"
        lines.append(
            f"Last result ({_day(date.fromisoformat(last['target_date']))}): we said "
            f"{last['direction']}, the market was {last['actual_direction']} "
            f"({last['actual_change_pct']:+.2f}%). We were {verdict}."
        )
    record = data["track_record"]
    if record["total"]:
        line = (
            f"Track record: {record['correct']} of {record['total']} right "
            f"({record['accuracy'] * 100:.0f}%). Simple baseline: "
            f"{record['baseline_accuracy'] * 100:.0f}%."
        )
        if not record["enough_results"]:
            line += f" Only {record['total']} results. Wait for {MIN_RESULTS_TO_TRUST}."
        lines.append(line)
    else:
        lines.append("Track record: no results yet.")
    return lines


def _render_story(item: dict) -> list[str]:
    head = f"• {item['title']} ({item['source']}, {item['score']:+.1f})"
    lines = [head]
    if item["reason"]:
        lines.append(f"  {item['reason']}")
    if item["companies"]:
        lines.append("  Companies: " + ", ".join(item["companies"]))
    lines.append(f"  {item['url']}")
    return lines


def _render_news(news: dict) -> list[str]:
    lines = ["NEWS SINCE THE LAST CLOSE"]
    if not news["articles"]:
        lines.append("No scored news. The news or the LLM service may be down.")
        return lines
    neutral = news["articles"] - news["positive"] - news["negative"]
    lines.append(
        f"{news['articles']} important articles: {news['positive']} good, "
        f"{news['negative']} bad, {neutral} neutral."
    )
    if news["good"]:
        lines.append("Good:")
        for item in news["good"]:
            lines.extend(_render_story(item))
    if news["bad"]:
        lines.append("Bad:")
        for item in news["bad"]:
            lines.extend(_render_story(item))
    return lines


def _render_ipos(ipos: dict) -> list[str]:
    lines = ["IPOS"]
    empty = True
    if ipos["listing_today"]:
        empty = False
        lines.append("Listing today:")
        lines.extend(_ipo_line(i, show_verdict=False) for i in ipos["listing_today"])
    if ipos["open_now"]:
        empty = False
        lines.append("Open now:")
        lines.extend(_ipo_line(i) for i in ipos["open_now"])
    if ipos["upcoming"]:
        empty = False
        lines.append(f"Coming in the next {ipos['days_ahead']} days:")
        lines.extend(_ipo_line(i) for i in ipos["upcoming"])
    if empty:
        lines.append(f"No IPO is open, listing, or coming in the next {ipos['days_ahead']} days.")
    if ipos["likely_good"]:
        lines.append("Likely to do well (our rule, not a promise):")
        lines.extend(f"• {i['name']} (score {i['score']:+.2f})" for i in ipos["likely_good"])
    if ipos["without_verdict"]:
        count = ipos["without_verdict"]
        subject = "1 IPO has" if count == 1 else f"{count} IPOs have"
        lines.append(
            f"{subject} no verdict: the GMP or the subscription is not entered. "
            "The GMP is not official data."
        )
    return lines


def render_text(data: dict) -> str:
    """Make the plain text of the report from the data."""
    day = date.fromisoformat(data["date"])
    sections = [
        [f"KASH ENGINE: DAILY REPORT, {_day(day)} {day.year}"],
        _render_outlook(data),
        _render_news(data["news"]),
        _render_ipos(data["ipos"]),
        ["This is an automated summary for information. It is not investment advice."],
    ]
    return "\n\n".join("\n".join(section) for section in sections)


# --- Saving --------------------------------------------------------------------------------


def _refresh_ipos(day: date, now: datetime) -> None:
    """Update the IPO status and scores, so the report shows the newest GMP and subscription.

    This reads only the database. If it fails, the report is still built with the saved scores.
    """
    try:
        refresh_statuses(day)
        score_ipos(now)
    except Exception:
        logger.exception("The IPO scores could not be updated. The report uses the saved scores.")


def build_report(
    day: date | None = None, now: datetime | None = None, force: bool = False
) -> tuple[Report, bool]:
    """Build and save the report for a day. Return (report, created).

    - The day is today (IST). The prediction is for the next trading day from that day.
    - If a report for the day exists, it is returned and not changed, so a second run (or the
      retry) sends the same text. force=True builds it again.
    - If there is no prediction yet, it is made now.
    """
    now = now or timezone.now()
    day = day or today_ist(now)
    existing = Report.objects.filter(date=day).first()
    if existing and not force:
        return existing, False

    _refresh_ipos(day, now)
    prediction, _ = make_prediction(next_trading_day(day), now=now)
    data = gather(day, prediction)
    report, _ = Report.objects.update_or_create(
        date=day,
        defaults={
            "text": render_text(data),
            "prediction": prediction.direction,
            "confidence": prediction.confidence,
            "data": data,
        },
    )
    logger.info("Report for %s built (%d characters)", day, len(report.text))
    return report, True
