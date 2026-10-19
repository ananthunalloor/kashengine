"""Private Markets preview, sharing the legacy page's queries and evaluation rules."""

from django.http import HttpRequest
from django.template.defaultfilters import floatformat
from ninja import Router

from apps.api.v1.common import ERRORS
from apps.markets.evaluation import accuracy_stats
from apps.reports.formatting import score_out_of_ten
from apps.web.queries import latest_quotes, prediction_history
from apps.web.templatetags.web_extras import percent, signed

from .auth import AppSession
from .schemas import Markets

router = Router(tags=["Markets"], auth=AppSession("markets"))


def market_stats() -> dict:
    """Format saved accuracy statistics for the private Markets and Today pages.

    Returns:
        Existing evaluation statistics with formatted accuracy and baseline percentages.
    """
    stats = accuracy_stats()
    return {
        **stats,
        "accuracy": percent(stats["accuracy"]),
        "baseline_accuracy": percent(stats["baseline_accuracy"]),
    }


def market_quotes() -> list[dict]:
    """Format the latest configured closes without fetching new prices.

    Returns:
        Instrument names, actual trading dates, closes and signed percentage changes.
    """
    return [
        {
            "name": quote["name"],
            "day": quote["day"],
            "close": floatformat(quote["close"], 2),
            "change": f"{signed(quote['change_pct'], 2)}%"
            if quote["change_pct"] is not None
            else "–",
        }
        for quote in latest_quotes()
    ]


@router.get(
    "/markets",
    response={200: Markets, **ERRORS},
    operation_id="get_app_markets",
    summary="Read market closes, prediction history, and accuracy",
)
def get_markets(request: HttpRequest):
    """Read saved results without fetching quotes or evaluating predictions."""
    return {
        "stats": market_stats(),
        "quotes": market_quotes(),
        "history": [
            {
                "date": prediction.target_date,
                "direction": prediction.direction,
                "strength": score_out_of_ten(prediction.confidence),
                "actual_direction": prediction.actual_direction,
                "change": f"{signed(prediction.actual_change_pct, 2)}%"
                if prediction.actual_change_pct is not None
                else "–",
                "result": "Right"
                if prediction.correct is True
                else "Wrong"
                if prediction.correct is False
                else "No session"
                if prediction.evaluated_at
                else "Waiting",
            }
            for prediction in prediction_history()
        ],
    }
