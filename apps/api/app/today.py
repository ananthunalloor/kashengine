"""Read-only Today preview, reusing the existing dashboard selections and formatting."""

from datetime import timedelta

from django.http import HttpRequest
from django.utils import timezone
from ninja import Router

from apps.access.middleware import access_for
from apps.api.errors import ApiError
from apps.api.v1.common import ERRORS
from apps.markets.models import Prediction
from apps.markets.trading import today_ist
from apps.reports.builder import gather_news
from apps.reports.formatting import score_out_of_ten
from apps.reports.models import Report
from apps.web.queries import DASHBOARD_ITEMS, NEWS_WINDOW_HOURS, dashboard_ipos, outlook
from apps.web.templatetags.web_extras import rupees, signed, times

from .auth import AppSession
from .markets import company_movers, market_quotes, market_stats
from .reports import summary as report_summary
from .schemas import Today
from .stocks_watch import stocks_to_watch

router = Router(tags=["Today"], auth=AppSession())


@router.get(
    "/today",
    response={200: Today, **ERRORS},
    operation_id="get_app_today",
    summary="Read the daily overview for the current account's available features",
)
def get_today(request: HttpRequest):
    """Gate each section before reading it; never refresh providers or write forecasts.

    Args:
        request: The authenticated browser request with feature/subscription access.

    Returns:
        Saved dashboard sections; unavailable features contain no data.

    Raises:
        ApiError: When the current subscription does not permit dashboard access.
    """
    access = access_for(request)
    if not access.subscription_ok:
        raise ApiError("subscription_required", "An active trial or subscription is needed.")
    now = timezone.now()
    today = today_ist(now)
    result = {"today": today, "markets": None, "news": None, "ipos": None, "report": None}
    result["stocks_watch"] = (
        stocks_to_watch(now)
        if all(access.can(feature) for feature in ("companies", "markets", "news"))
        else None
    )
    if access.can("markets"):
        saved = outlook(Prediction.objects.order_by("-target_date").first())
        formatted = None
        if saved is not None:
            prediction = saved["prediction"]
            formatted = {
                "date": prediction.target_date,
                "direction": prediction.direction,
                "strength": score_out_of_ten(prediction.confidence),
                "strength_label": saved["strength"],
                "news_score": score_out_of_ten(prediction.news_score, signed=True),
                "news_articles": prediction.news_articles,
                "global_score": score_out_of_ten(prediction.global_score, signed=True),
                "cues": [
                    {
                        "name": cue["name"],
                        "change": f"{signed(cue['change_pct'], 2)}%"
                        if cue["change_pct"] is not None
                        else "–",
                        "as_of": cue["as_of"],
                    }
                    for cue in saved["cues"]
                ],
                "notes": saved["notes"],
            }
        result["markets"] = {
            "outlook": formatted,
            "stats": market_stats(),
            "quotes": market_quotes(),
            "movers": company_movers(),
        }
    if access.can("news"):
        news = gather_news(now - timedelta(hours=NEWS_WINDOW_HOURS), limit=DASHBOARD_ITEMS)
        result["news"] = {
            **news,
            **{
                group: [
                    {**story, "score": score_out_of_ten(story["score"], signed=True)}
                    for story in news[group]
                ]
                for group in ("good", "bad")
            },
        }
    if access.can("ipos"):
        groups = dashboard_ipos(today)
        result["ipos"] = {
            "days_ahead": groups["days_ahead"],
            **{
                group: [
                    {
                        **issue,
                        "price_band": rupees(issue["price_band_high"]),
                        "gmp": f"{signed(issue['gmp_pct'])}%"
                        if issue["gmp_pct"] is not None
                        else "–",
                        "subscribed": times(issue["subscription_times"]),
                        "score": score_out_of_ten(issue["score"], signed=True)
                        if issue["score"] is not None
                        else None,
                    }
                    for issue in groups[group]
                ]
                for group in ("likely_good", "open_now", "upcoming")
            },
        }
    if access.can("reports"):
        report = Report.objects.first()
        result["report"] = report_summary(report) if report is not None else None
    return result
