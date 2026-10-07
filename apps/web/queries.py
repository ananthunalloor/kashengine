"""The data for the web pages. These functions only read the database."""

from datetime import date, datetime, timedelta

from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from apps.companies.models import Company
from apps.ipos.models import Ipo
from apps.markets.evaluation import accuracy_stats
from apps.markets.instruments import ALL_INSTRUMENTS
from apps.markets.models import IndexQuote, Prediction
from apps.markets.trading import today_ist
from apps.news.models import NewsArticle
from apps.reports.builder import STORY_MIN_SCORE, gather_ipos, gather_news
from apps.reports.builder import _strength as strength_label
from apps.reports.models import Report

SENTIMENT_FILTERS = {
    "positive": "Good news",
    "negative": "Bad news",
    "neutral": "Neutral",
    "unscored": "Not scored yet",
}
IPO_TABS = {
    "": "Active",
    "open": "Open",
    "upcoming": "Upcoming",
    "closed": "Closed",
    "listed": "Listed",
    "all": "All",
}
VERDICT_FILTERS = {"good": "Likely good", "mixed": "Mixed", "weak": "Weak", "unknown": "No verdict"}
CATEGORY_FILTERS = {"mainboard": "Mainboard", "sme": "SME"}
NEWS_WINDOW_HOURS = 36
DASHBOARD_ITEMS = 4


# --- Markets -------------------------------------------------------------------------------


def latest_quotes() -> list[dict]:
    """The newest saved close of each instrument. Instruments without data are left out."""
    rows = []
    for instrument in ALL_INSTRUMENTS:
        quote = IndexQuote.objects.filter(symbol=instrument.symbol).order_by("-day").first()
        if quote is not None:
            rows.append(
                {
                    "name": instrument.name,
                    "day": quote.day,
                    "close": quote.close,
                    "change_pct": quote.change_pct,
                }
            )
    return rows


def outlook(prediction: Prediction | None) -> dict | None:
    """The prediction in the form that the pages show."""
    if prediction is None:
        return None
    cues = sorted(
        prediction.inputs.get("cues", []),
        key=lambda c: abs(c.get("weight", 0) * c.get("signal", 0)),
        reverse=True,
    )
    return {
        "prediction": prediction,
        "strength": strength_label(prediction.confidence),
        "cues": cues[:5],
        "notes": prediction.inputs.get("notes", []),
    }


def prediction_history(limit: int = 30) -> list[Prediction]:
    return list(Prediction.objects.all()[:limit])


# --- Dashboard -----------------------------------------------------------------------------


def _ipo_groups(today: date) -> dict:
    """The IPO lists for the dashboard. An IPO is in one list only. Dates are real dates."""
    groups = gather_ipos(today, limit=DASHBOARD_ITEMS)
    shown = {item["name"] for item in groups["likely_good"]}
    for key in ("open_now", "upcoming"):
        groups[key] = [item for item in groups[key] if item["name"] not in shown]
    for key in ("likely_good", "open_now", "upcoming", "listing_today"):
        for item in groups[key]:
            for field in ("open_date", "close_date", "listing_date"):
                if item[field]:
                    item[field] = date.fromisoformat(item[field])
    return groups


def dashboard_data(now: datetime | None = None) -> dict:
    now = now or timezone.now()
    today = today_ist(now)
    return {
        "today": today,
        "outlook": outlook(Prediction.objects.order_by("-target_date").first()),
        "report": Report.objects.first(),
        "stats": accuracy_stats(),
        "ipos": _ipo_groups(today),
        "news": gather_news(now - timedelta(hours=NEWS_WINDOW_HOURS), limit=DASHBOARD_ITEMS),
        "quotes": latest_quotes(),
    }


# --- News ----------------------------------------------------------------------------------


def news_sources() -> list[str]:
    return list(NewsArticle.objects.order_by("source").values_list("source", flat=True).distinct())


def news_queryset(filters: dict[str, str]):
    articles = NewsArticle.objects.prefetch_related("companies")
    if filters["q"]:
        articles = articles.filter(
            Q(title__icontains=filters["q"]) | Q(summary__icontains=filters["q"])
        )
    if filters["source"]:
        articles = articles.filter(source=filters["source"])
    match filters["sentiment"]:
        case "positive":
            articles = articles.filter(sentiment_score__gte=STORY_MIN_SCORE)
        case "negative":
            articles = articles.filter(sentiment_score__lte=-STORY_MIN_SCORE)
        case "neutral":
            articles = articles.filter(
                sentiment_score__gt=-STORY_MIN_SCORE, sentiment_score__lt=STORY_MIN_SCORE
            )
        case "unscored":
            articles = articles.filter(scored_at__isnull=True)
    return articles


# --- IPOs ----------------------------------------------------------------------------------


def ipo_queryset(filters: dict[str, str]):
    ipos = Ipo.objects.all()
    tab = filters["status"] if filters["status"] in IPO_TABS else ""
    if tab == "":
        ipos = ipos.exclude(status=Ipo.Status.LISTED).annotate(
            rank=Case(
                When(status=Ipo.Status.OPEN, then=Value(0)),
                When(status=Ipo.Status.UPCOMING, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        )
        ipos = ipos.order_by("rank", "open_date", "name")
    elif tab == "listed":
        ipos = ipos.filter(status=Ipo.Status.LISTED).order_by("-listing_date", "name")
    elif tab != "all":
        ipos = ipos.filter(status=tab)
    if filters["verdict"] in VERDICT_FILTERS:
        if filters["verdict"] == "unknown":
            ipos = ipos.filter(Q(verdict="") | Q(verdict="unknown"))
        else:
            ipos = ipos.filter(verdict=filters["verdict"])
    if filters["category"] in CATEGORY_FILTERS:
        ipos = ipos.filter(category=filters["category"])
    if filters["q"]:
        ipos = ipos.filter(name__icontains=filters["q"])
    return ipos


# --- Companies -----------------------------------------------------------------------------


def company_queryset(filters: dict[str, str]):
    companies = Company.objects.order_by("name")
    if filters["q"]:
        companies = companies.filter(
            Q(name__icontains=filters["q"])
            | Q(symbol__icontains=filters["q"])
            | Q(sector__icontains=filters["q"])
        )
    return companies


def _day(value: date | None) -> str:
    return f"{value:%a} {value.day} {value:%b %Y}" if value else "–"


def _age(stamp: datetime | None, now: datetime) -> str:
    if stamp is None:
        return ""
    hours = (now - stamp).total_seconds() / 3600
    if hours < 1:
        return " (updated less than an hour ago)"
    if hours < 48:
        return f" (updated {int(hours)} hours ago)"
    return f" (updated {int(hours // 24)} days ago)"


def ipo_facts(ipo: Ipo, now: datetime) -> list[tuple[str, str]]:
    """The (label, text) rows for the detail page of an IPO."""
    band = "–"
    if ipo.price_band_high:
        low = ipo.price_band_low
        band = (
            f"₹{low:,.0f} to ₹{ipo.price_band_high:,.0f}"
            if low and low != ipo.price_band_high
            else f"₹{ipo.price_band_high:,.0f}"
        )
    gmp = "–"
    if ipo.gmp is not None:
        pct = ipo.gmp_pct
        gmp = f"₹{ipo.gmp:,.0f}" + (f" ({pct:+.1f}%)" if pct is not None else "")
        gmp += _age(ipo.gmp_updated_at, now)
    subscription = "–"
    if ipo.subscription_times is not None:
        subscription = f"{ipo.subscription_times:,.1f}x" + _age(ipo.subscription_updated_at, now)
    gain = "–" if ipo.listing_gain_pct is None else f"{ipo.listing_gain_pct:+.1f}%"
    return [
        ("Opens", _day(ipo.open_date)),
        ("Closes", _day(ipo.close_date)),
        ("Lists", _day(ipo.listing_date)),
        ("Price band", band),
        ("Lot size", f"{ipo.lot_size:,}" if ipo.lot_size else "–"),
        ("Issue size", f"₹{ipo.issue_size_cr:,.0f} crore" if ipo.issue_size_cr else "–"),
        ("GMP", gmp),
        ("Subscribed", subscription),
        ("Listing price", f"₹{ipo.listing_price:,.2f}" if ipo.listing_price else "–"),
        ("Listing gain", gain),
    ]
