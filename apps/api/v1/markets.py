"""Market outlook, prediction history, accuracy and quotes: `/api/v1/markets/...`."""

from django.http import Http404, HttpRequest
from ninja import Query, Router

from apps.markets.evaluation import accuracy_stats
from apps.markets.models import Prediction
from apps.web import queries

from ..auth import for_feature
from ..pagination import PageParams, paginate
from .common import ERRORS, ERRORS_WITH_VALIDATION
from .schemas import Accuracy, Outlook, PredictionItem, PredictionPage, Quote

router = Router(tags=["Markets"], auth=for_feature("markets"))


@router.get(
    "/markets/outlook",
    response={200: Outlook, **ERRORS},
    operation_id="get_outlook",
    summary="Get the newest market prediction",
)
def get_outlook(request: HttpRequest):
    """Return the newest prediction for the target index (Nifty 50).

    `confidence` shows how strong the signal is. It is not a probability. Compare it with the
    numbers of `/markets/accuracy`. The answer is `404` before the first prediction exists.

    **Required feature:** `markets`.
    """
    prediction = Prediction.objects.order_by("-target_date").first()
    if prediction is None:
        raise Http404
    if prediction.direction == "withheld":
        raise Http404("The newest prediction was withheld by the data-quality watchdog.")
    outlook = queries.outlook(prediction)
    assert outlook is not None  # noqa: S101 - a prediction object always gives an outlook.
    base = PredictionItem.model_validate(prediction, from_attributes=True).model_dump()
    return Outlook(
        **base, strength=outlook["strength"], cues=outlook["cues"], notes=outlook["notes"]
    )


@router.get(
    "/markets/predictions",
    response={200: PredictionPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_predictions",
    summary="List past predictions",
)
def list_predictions(request: HttpRequest, params: Query[PageParams]):
    """List predictions, newest target date first, with the real result when it is known.

    **Required feature:** `markets`.
    """
    return paginate(Prediction.objects.exclude(direction="withheld"), params)


@router.get(
    "/markets/accuracy",
    response={200: Accuracy, **ERRORS},
    operation_id="get_accuracy",
    summary="Get the accuracy of the predictions",
)
def get_accuracy(request: HttpRequest):
    """Return how often the predictions were right, and the baseline to compare with.

    The baseline always guesses the most common real direction. A useful model must beat it.
    Trust the numbers only when `enough_results` is true.

    **Required feature:** `markets`.
    """
    return accuracy_stats()


@router.get(
    "/markets/quotes",
    response={200: list[Quote], **ERRORS},
    operation_id="list_quotes",
    summary="List the newest quotes",
)
def list_quotes(request: HttpRequest):
    """Return the newest saved close of each enabled instrument.

    An instrument with no saved quote is left out. The list is short, so it has no paging.

    **Required feature:** `markets`.
    """
    return queries.latest_quotes()
