"""Request and response schemas of API v1.

These classes are the contract. The OpenAPI file (`docs/openapi/v1.json`) is made from them.
Inside v1 you may add a new optional field. You may not remove a field, rename it, or change
its type. See `docs/docs/api/versioning.md`.
"""

from datetime import date, datetime
from typing import Any, Literal

from ninja import Field, Schema

from apps.reports.builder import STORY_MIN_SCORE

Day = date  # An alias. A field named `date` hides the type `date` inside its own class.
Sentiment = Literal["positive", "negative", "neutral", "unscored"]
Direction = Literal["up", "down", "flat"]
IpoStatus = Literal["upcoming", "open", "closed", "listed"]
IpoVerdict = Literal["good", "mixed", "weak", "unknown"]
IpoCategory = Literal["mainboard", "sme"]


# ----------------------------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------------------------
class FieldError(Schema):
    """One wrong parameter in a `validation_error`."""

    field: str = Field(description="The name of the parameter.")
    message: str = Field(description="What is wrong.")
    type: str = Field(description="A short machine-readable reason, for example `int_parsing`.")


class Problem(Schema):
    """An error answer (RFC 9457). The content type is `application/problem+json`."""

    type: str = Field(description="A link to the explanation of the code.")
    title: str = Field(description="The HTTP status text.")
    status: int = Field(description="The HTTP status code.")
    detail: str = Field(description="What went wrong in this case. Safe to show to a user.")
    instance: str = Field(description="The path of the request.")
    code: str = Field(description="A stable code. Branch on this value, not on `detail`.")
    errors: list[FieldError] | None = Field(
        None, description="The wrong parameters. Only for `validation_error`."
    )


# ----------------------------------------------------------------------------------------
# Service
# ----------------------------------------------------------------------------------------
class Health(Schema):
    """The state of the API."""

    status: Literal["ok"] = Field(description="Always `ok` when the API answers.")
    version: str = Field(description="The full version of the API contract, for example 1.0.0.")


class TokenInfo(Schema):
    """The token that made the request. It never holds the secret."""

    name: str = Field(description="The label that the owner chose.")
    prefix: str = Field(description="The eight public characters of the token.")
    created_at: datetime = Field(description="When the token was made.")
    expires_at: datetime | None = Field(None, description="Empty means the token does not expire.")
    last_used_at: datetime | None = Field(
        None,
        description="When the token was last used. The server updates it at most once a minute.",
    )


class SubscriptionInfo(Schema):
    """The subscription of the caller."""

    kind: Literal["trial", "paid", "gift"] = Field(description="How the subscription started.")
    state: Literal["trial", "active", "expired", "none", "staff"] = Field(
        description="`staff` means: staff and superusers need no subscription."
    )
    started_at: datetime = Field(description="When the subscription started.")
    ends_at: datetime | None = Field(None, description="Empty means the subscription does not end.")
    days_left: int | None = Field(None, description="Whole days to the end. Empty if no end.")


class Me(Schema):
    """The caller, the subscription, and the features of the account."""

    id: int = Field(description="The user id.")
    username: str = Field(description="The user name.")
    is_staff: bool = Field(description="True for a staff or superuser account.")
    subscription_required: bool = Field(
        description="True if an admin turned on the rule that a user needs a subscription."
    )
    subscription: SubscriptionInfo | None = Field(
        None, description="The subscription row. Empty if the user has none."
    )
    features: list[str] = Field(description="The feature keys that the caller may use now.")
    token: TokenInfo | None = Field(
        None, description="Set when the request used a bearer token. Empty for a session."
    )


# ----------------------------------------------------------------------------------------
# Reports
# ----------------------------------------------------------------------------------------
class ReportSummary(Schema):
    """One daily report, without its text."""

    date: Day = Field(description="The date of the report. There is one report for each date.")
    prediction: Direction | None = Field(None, description="The predicted market direction.")
    confidence: float | None = Field(None, ge=0, le=1, description="Signal strength, 0 to 1.")
    created_at: datetime = Field(description="When the server saved the report.")

    @staticmethod
    def resolve_prediction(obj: Any) -> str | None:
        """Turn an empty text into null.

        Args:
            obj: The report row.

        Returns:
            The prediction text, or None if it is empty.
        """
        return obj.prediction or None


class ReportDetail(ReportSummary):
    """One daily report with its text and data."""

    text: str = Field(description="The full report text that is sent on Telegram.")
    data: dict[str, Any] = Field(
        description="The numbers and lists behind the text. The keys can grow. "
        "Do not depend on a key that is not in the developer guide."
    )


class ReportPage(Schema):
    """A page of reports."""

    items: list[ReportSummary] = Field(description="The rows of this page.")
    count: int = Field(description="The number of rows in all pages, with the filters applied.")
    limit: int = Field(description="The page size that the server used.")
    offset: int = Field(description="The number of rows that the server skipped.")


# ----------------------------------------------------------------------------------------
# News
# ----------------------------------------------------------------------------------------
class CompanyRef(Schema):
    """A company that is named in an article."""

    symbol: str = Field(description="The NSE symbol of the company.")
    name: str = Field(description="The company name.")


class NewsItem(Schema):
    """One scored news article. The full text is not part of the API."""

    id: int = Field(description="The article id.")
    source: str = Field(description="The source name, for example Moneycontrol.")
    title: str = Field(description="The headline.")
    url: str = Field(description="The link to the article on the site of the source.")
    summary: str = Field(description="The short text from the RSS feed.")
    published_at: datetime | None = Field(
        None, description="When the source published the article. Empty if the feed gave no date."
    )
    sentiment: Sentiment = Field(
        description="`unscored` until the model has scored the article. A score of at least 0.2 "
        "is `positive`, at most -0.2 is `negative`, and the rest is `neutral`."
    )
    sentiment_score: float | None = Field(
        None,
        ge=-1,
        le=1,
        description="From -1 (very negative) to 1 (very positive). Empty until scored.",
    )
    sentiment_reason: str = Field(
        "", description="The reason that the model gave for the score. Empty until scored."
    )
    relevance: float | None = Field(
        None, ge=0, le=1, description="How much the article matters to the Indian market."
    )
    scored_at: datetime | None = Field(
        None, description="When the model scored the article. Empty means not scored yet."
    )
    companies: list[CompanyRef] = Field(
        description="The companies that the server found in the article."
    )

    @staticmethod
    def resolve_sentiment(obj: Any) -> str:
        """Return the label that follows from the score.

        Args:
            obj: The news article row.

        Returns:
            `unscored` if the article has no score. Else `positive`, `negative` or `neutral`.
            The limit between them is `STORY_MIN_SCORE`.
        """
        score = obj.sentiment_score
        if obj.scored_at is None or score is None:
            return "unscored"
        if score >= STORY_MIN_SCORE:
            return "positive"
        return "negative" if score <= -STORY_MIN_SCORE else "neutral"

    @staticmethod
    def resolve_companies(obj: Any) -> list[Any]:
        """Return the matched companies (the list view prefetches them).

        Args:
            obj: The news article row.

        Returns:
            The company rows that are linked to the article.
        """
        return list(obj.companies.all())


class NewsPage(Schema):
    """A page of news articles."""

    items: list[NewsItem] = Field(description="The rows of this page.")
    count: int = Field(description="The number of rows in all pages, with the filters applied.")
    limit: int = Field(description="The page size that the server used.")
    offset: int = Field(description="The number of rows that the server skipped.")


# ----------------------------------------------------------------------------------------
# IPOs
# ----------------------------------------------------------------------------------------
class IpoItem(Schema):
    """One IPO with its dates, price, GMP, subscription and score."""

    id: int = Field(description="The IPO id.")
    name: str = Field(description="The name of the issue.")
    category: IpoCategory = Field(description="`mainboard` or `sme`.")
    status: IpoStatus = Field(description="`upcoming`, `open`, `closed` or `listed`.")
    open_date: date | None = Field(
        None, description="The first day of the bid. Empty if not known."
    )
    close_date: date | None = Field(
        None, description="The last day of the bid. Empty if not known."
    )
    listing_date: date | None = Field(
        None, description="The day of the listing. Empty if not known."
    )
    price_band_low: float | None = Field(None, description="Rupees.")
    price_band_high: float | None = Field(None, description="Rupees.")
    lot_size: int | None = Field(None, description="The number of shares in one lot.")
    issue_size_cr: float | None = Field(None, description="Crore rupees.")
    gmp: float | None = Field(None, description="Grey market premium, rupees.")
    gmp_pct: float | None = Field(None, description="GMP in percent of the upper price band.")
    gmp_updated_at: datetime | None = Field(
        None, description="When the GMP was last set or confirmed."
    )
    subscription_times: float | None = Field(None, description="Total subscription, in times.")
    subscription_updated_at: datetime | None = Field(
        None, description="When the subscription was last set or confirmed."
    )
    listing_price: float | None = Field(None, description="Rupees. Set after the listing.")
    listing_gain_pct: float | None = Field(None, description="Percent. Set after the listing.")
    score: float | None = Field(
        None,
        ge=-1,
        le=1,
        description="The score of the IPO, from -1 (weak) to 1 (good). Empty until scored.",
    )
    verdict: IpoVerdict | None = Field(None, description="Empty until the IPO is scored.")
    scored_at: datetime | None = Field(None, description="When the IPO was scored.")
    nse_symbol: str = Field("", description="The NSE symbol after the listing. Empty before.")
    company: CompanyRef | None = Field(
        None, description="The company row that matches the IPO. Empty if there is none."
    )

    @staticmethod
    def resolve_verdict(obj: Any) -> str | None:
        """Turn an empty text into null.

        Args:
            obj: The IPO row.

        Returns:
            The verdict text, or None if it is empty.
        """
        return obj.verdict or None


class IpoSignal(Schema):
    """One input of the IPO score."""

    name: str = Field(description="`gmp`, `subscription` or `news`.")
    value: float = Field(description="The raw number: GMP percent, subscription times, ...")
    signal: float = Field(ge=-1, le=1, description="The value on the scale -1 (bad) to 1 (good).")
    strength: float = Field(ge=0, le=1, description="How much we trust the input, 0 to 1.")


class IpoDetail(IpoItem):
    """One IPO with the inputs of its score."""

    signals: list[IpoSignal] = Field(
        description="The inputs of the score. Empty until the IPO is scored."
    )
    notes: list[str] = Field(description="Why an input was not used.")
    source_url: str = Field("", description="The page that the data came from. Empty if not known.")

    @staticmethod
    def resolve_signals(obj: Any) -> list[dict[str, Any]]:
        """Return the signals saved with the score.

        Args:
            obj: The IPO row.

        Returns:
            The `signals` list of `score_inputs`. It is empty if the IPO has no score.
        """
        return (obj.score_inputs or {}).get("signals", [])

    @staticmethod
    def resolve_notes(obj: Any) -> list[str]:
        """Return the notes saved with the score.

        Args:
            obj: The IPO row.

        Returns:
            The `notes` list of `score_inputs`. It is empty if the IPO has no score.
        """
        return (obj.score_inputs or {}).get("notes", [])


class IpoPage(Schema):
    """A page of IPOs."""

    items: list[IpoItem] = Field(description="The rows of this page.")
    count: int = Field(description="The number of rows in all pages, with the filters applied.")
    limit: int = Field(description="The page size that the server used.")
    offset: int = Field(description="The number of rows that the server skipped.")


# ----------------------------------------------------------------------------------------
# Markets
# ----------------------------------------------------------------------------------------
class Cue(Schema):
    """One global cue and its part in a prediction."""

    symbol: str = Field(description="The Yahoo Finance symbol, for example `^GSPC`.")
    name: str = Field(description="The display name.")
    change_pct: float = Field(
        description="The change from the close of the day before, in percent."
    )
    as_of: str = Field(description="The trading day of the quote, `YYYY-MM-DD`.")
    weight: float = Field(description="From -1 to 1. A minus sign means a rise is bad news.")
    signal: float = Field(description="The change on the scale -1 to 1.")


class PredictionItem(Schema):
    """The prediction for one trading day, and later the real result."""

    target_date: date = Field(description="The trading day that the prediction is for.")
    direction: Direction = Field(description="The predicted direction.")
    confidence: float = Field(
        ge=0, le=1, description="How strong the signal is. It is not a probability."
    )
    score: float = Field(ge=-1, le=1, description="From -1 (down) to 1 (up).")
    news_score: float | None = Field(
        None, description="The part of the score from news. Empty if no news was used."
    )
    global_score: float | None = Field(
        None, description="The part of the score from global markets. Empty if no cue was used."
    )
    news_articles: int = Field(description="The number of articles in the news score.")
    created_at: datetime = Field(description="When the server made the prediction.")
    actual_direction: Direction | None = Field(None, description="Empty until the result is known.")
    actual_change_pct: float | None = Field(
        None,
        description="The real change of the index, in percent. Empty until the result is known.",
    )
    correct: bool | None = Field(
        None, description="Empty means no result yet, or no trading session on that day."
    )
    evaluated_at: datetime | None = Field(
        None, description="When the server compared the prediction with the result."
    )

    @staticmethod
    def resolve_actual_direction(obj: Any) -> str | None:
        """Turn an empty text into null.

        Args:
            obj: The prediction row.

        Returns:
            The real direction, or None if the prediction is not evaluated yet.
        """
        return obj.actual_direction or None


class Outlook(PredictionItem):
    """The newest prediction with its strength label and its biggest inputs."""

    strength: Literal["weak", "moderate", "strong"] = Field(
        description="A label for `confidence`: `weak`, `moderate` or `strong`."
    )
    cues: list[Cue] = Field(description="The five inputs with the biggest effect.")
    notes: list[str] = Field(description="Facts that reduce trust, for example missing cues.")


class PredictionPage(Schema):
    """A page of predictions, newest first."""

    items: list[PredictionItem] = Field(description="The rows of this page.")
    count: int = Field(description="The number of rows in all pages, with the filters applied.")
    limit: int = Field(description="The page size that the server used.")
    offset: int = Field(description="The number of rows that the server skipped.")


class Tally(Schema):
    """A number of predictions and how many of them were right."""

    n: int = Field(description="The number of predictions.")
    correct: int = Field(description="How many of them were right.")


class Accuracy(Schema):
    """How good the predictions were. Compare `accuracy` with `baseline_accuracy`."""

    total: int = Field(description="Predictions with a result.")
    correct: int = Field(description="The number of predictions that were right.")
    accuracy: float | None = Field(None, description="`correct / total`. Empty if no result.")
    by_prediction: dict[str, Tally] = Field(
        description="The result for each predicted direction. The keys are `up`, `down` and `flat`."
    )
    actual_counts: dict[str, int] = Field(description="How often each real direction happened.")
    baseline_direction: str | None = Field(
        None, description="The most common real direction. Always guessing it is the baseline."
    )
    baseline_accuracy: float | None = Field(
        None,
        description="The accuracy of always guessing `baseline_direction`. Empty if no result.",
    )
    high_confidence: Tally
    recent: Tally
    void: int = Field(description="Predictions for a day without a trading session.")
    pending: int = Field(description="Predictions that wait for a result.")
    enough_results: bool = Field(description="False while `total` is too small to trust.")


class Quote(Schema):
    """The newest saved close of one instrument."""

    name: str = Field(description="The display name of the instrument.")
    day: date = Field(description="The trading day of the close.")
    close: float = Field(description="The closing value.")
    change_pct: float | None = Field(
        None,
        description="The change from the close of the day before, in percent. Empty if not known.",
    )


# ----------------------------------------------------------------------------------------
# Companies and delivery
# ----------------------------------------------------------------------------------------
class CompanyItem(Schema):
    """One listed company."""

    symbol: str = Field(description="The NSE symbol.")
    name: str = Field(description="The company name.")
    sector: str = Field("", description="The sector. Empty if not known.")
    aliases: list[str] = Field(
        description="Other names that the news matcher uses for this company."
    )
    screener_url: str = Field(
        "", description="The Screener.in page of the company. Empty if not known."
    )
    last_updated: datetime | None = Field(
        None, description="When the Screener.in data was fetched. Empty means never."
    )


class CompanyPage(Schema):
    """A page of companies."""

    items: list[CompanyItem] = Field(description="The rows of this page.")
    count: int = Field(description="The number of rows in all pages, with the filters applied.")
    limit: int = Field(description="The page size that the server used.")
    offset: int = Field(description="The number of rows that the server skipped.")


class DeliveryItem(Schema):
    """One try to send a report."""

    id: int = Field(description="The log row id.")
    report_date: date | None = Field(
        None, description="The date of the report that was sent. Empty if the report was deleted."
    )
    channel: Literal["telegram", "email"] = Field(description="The delivery channel.")
    status: Literal["sent", "failed"] = Field(description="`sent` or `failed`.")
    recipient: str = Field(description="Masked. Only the last four characters show.")
    error: str | None = Field(None, description="Only staff see the error text.")
    created_at: datetime = Field(description="When the server tried to send.")


class DeliveryPage(Schema):
    """A page of delivery log rows, newest first."""

    items: list[DeliveryItem] = Field(description="The rows of this page.")
    count: int = Field(description="The number of rows in all pages, with the filters applied.")
    limit: int = Field(description="The page size that the server used.")
    offset: int = Field(description="The number of rows that the server skipped.")
