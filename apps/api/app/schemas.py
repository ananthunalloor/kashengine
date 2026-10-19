"""Private application contracts, independent of the public v1 API."""

import datetime as dt
from datetime import datetime
from typing import Literal

from ninja import Field, Schema


class NavigationItem(Schema):
    """One visible link, calculated using the server's feature and subscription rules."""

    label: str = Field(description="Human-readable section name.")
    url: str = Field(description="Same-origin path to the existing section.")


class Session(Schema):
    """The current browser user's permissions and navigation."""

    id: int = Field(description="User primary key.")
    username: str = Field(description="Signed-in user's display name.")
    is_staff: bool = Field(description="Whether this user can read Ops pages.")
    is_superuser: bool = Field(description="Whether this user can perform Ops writes.")
    features: list[str] = Field(description="Feature keys currently available to this user.")
    subscription_required: bool = Field(description="Whether the site requires a subscription.")
    subscription_ok: bool = Field(description="Whether subscription rules permit feature access.")
    subscription_state: Literal["trial", "active", "expired", "none", "staff"] = Field(
        description="Current subscription state, or staff exemption."
    )
    notice: str = Field(description="Subscription warning; empty when there is no warning.")
    navigation: list[NavigationItem] = Field(description="Visible links, in menu order.")
    logout_url: str = Field(description="Same-origin Django logout endpoint; requires CSRF POST.")


class AccountFeature(Schema):
    """Access explanation for one feature, including removed and subscription-locked states."""

    key: str
    label: str
    help: str
    allowed: bool
    removed: bool


class AccountToken(Schema):
    """Token metadata only; never a hash, password stamp, or full secret."""

    id: int
    name: str
    display: str
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    state: Literal["active", "expired", "revoked"]


class Account(Schema):
    """Subscription, feature access, and token settings for the current browser user."""

    username: str
    email: str
    state: Literal["trial", "active", "expired", "none", "staff"]
    subscription_kind: str | None
    ends_at: datetime | None
    days_left: int | None
    subscription_ok: bool
    required: bool
    price: str = Field(description="Formatted period price, or empty when not charged.")
    currency: str
    period_days: int
    contact: str
    features: list[AccountFeature]
    api_enabled: bool
    api_docs: bool
    tokens: list[AccountToken] = Field(description="Newest 20 tokens, including revoked/expired.")
    active_tokens: int = Field(
        description="Active count across all tokens, not just the newest 20."
    )
    token_limit: int
    token_days: int


class TokenCreate(Schema):
    """Token name, validated without reflecting it in an error response."""

    name: str = Field(min_length=1, max_length=60)


class TokenCreated(Schema):
    """One-time creation answer, never included in a subsequent account read."""

    token: AccountToken
    secret: str = Field(description="Copy once; never cache or persist this response.")


class ReportSummary(Schema):
    """A report's date and outlook, without the full report text."""

    date: dt.date = Field(description="Trading date of the daily report.")
    prediction: str = Field(
        description="Outlook direction: up, down, flat, or empty if unavailable."
    )
    strength: str | None = Field(
        description="Formatted 1.0-10.0 signal strength, not a probability."
    )


class ReportPage(Schema):
    """A page of daily reports in newest-first order."""

    items: list[ReportSummary] = Field(description="Reports on this page.")
    page: int = Field(description="Resolved page number, starting at one.")
    pages: int = Field(description="Total number of pages; one for an empty list.")
    total: int = Field(description="Total number of reports.")
    page_size: int = Field(default=25, description="Resolved number of rows per page.")


class ReportDelivery(Schema):
    """Delivery status without recipient addresses or member-visible diagnostics."""

    id: int = Field(description="Delivery attempt primary key.")
    channel: str = Field(description="Human-readable delivery channel.")
    status: str = Field(description="Delivery status key: sent or failed.")
    status_label: str = Field(description="Human-readable delivery status.")
    created_at: datetime = Field(description="Time of the delivery attempt.")
    error: str | None = Field(description="Failure diagnostic for staff only; otherwise null.")


class ReportDetail(ReportSummary):
    """The display report and its delivery history."""

    text: str = Field(description="Display text, reformatted from saved data when available.")
    deliveries: list[ReportDelivery] = Field(description="Delivery attempts, newest first.")
    older: dt.date | None = Field(description="Date of the nearest older report, if any.")
    newer: dt.date | None = Field(description="Date of the nearest newer report, if any.")


class NewsItem(Schema):
    """An article's display fields, excluding scraped text and internal processing state."""

    id: int = Field(description="Article primary key.")
    title: str = Field(description="Original article headline, rendered as plain text.")
    url: str = Field(description="Original source URL; the browser only links HTTP(S) URLs.")
    source: str = Field(description="Publisher name.")
    published_at: datetime | None = Field(description="Publication time, when known.")
    sentiment: Literal["positive", "negative", "neutral", "unscored"] = Field(
        description="Display tone using the existing sentiment thresholds."
    )
    score: str | None = Field(description="Signed sentiment formatted on the 1.0-10.0 scale.")
    relevance: str | None = Field(description="Relevance formatted on the 1.0-10.0 scale.")
    reason: str = Field(description="Model explanation, rendered as plain text.")
    companies: list[str] = Field(description="Up to four linked company names.")


class NewsFilterOption(Schema):
    """One server-supported sentiment filter."""

    value: str = Field(description="Filter query value.")
    label: str = Field(description="Human-readable filter name.")


class NewsPage(Schema):
    """Filtered news and the available filter options."""

    items: list[NewsItem] = Field(description="Matching articles in the existing web order.")
    page: int = Field(description="Resolved page number, starting at one.")
    pages: int = Field(description="Total pages; one when empty.")
    total: int = Field(description="Total matching articles.")
    sources: list[str] = Field(description="All source names, sorted, independent of the filters.")
    sentiments: list[NewsFilterOption] = Field(description="Supported sentiment filters.")
    page_size: int = Field(default=25, description="Resolved number of rows per page.")


class IpoSummary(Schema):
    """Display values for one IPO, using the existing web formatting rules."""

    id: int = Field(description="IPO primary key.")
    name: str = Field(description="IPO company name.")
    category: str = Field(description="Human-readable board name.")
    status: str = Field(description="Human-readable issue status.")
    dates: str = Field(description="Opening and closing dates, or a dash when unknown.")
    price_band: str = Field(description="Upper price band in rupees, or a dash.")
    gmp: str = Field(description="Grey market premium as a signed percentage, or a dash.")
    subscribed: str = Field(description="Subscription in times, or a dash.")
    listing_gain: str = Field(description="Signed listing gain percentage, or a dash.")
    verdict: str = Field(description="Verdict key; unknown when there is insufficient data.")
    score: str | None = Field(description="Signed score on the 1.0-10.0 scale, if available.")


class IpoFilterOption(Schema):
    """A server-supported IPO filter choice."""

    value: str = Field(description="Query parameter value.")
    label: str = Field(description="Human-readable option label.")


class IpoPage(Schema):
    """Filtered IPOs and all supported filter choices."""

    items: list[IpoSummary] = Field(description="Matching IPOs in the existing web order.")
    page: int = Field(description="Resolved page number, starting at one.")
    pages: int = Field(description="Total pages; one for an empty list.")
    total: int = Field(description="Total matching IPOs.")
    statuses: list[IpoFilterOption] = Field(description="Status filters, including Active and All.")
    verdicts: list[IpoFilterOption] = Field(description="Verdict filters.")
    categories: list[IpoFilterOption] = Field(description="Board filters.")
    page_size: int = Field(default=25, description="Resolved number of rows per page.")


class IpoFact(Schema):
    """A labeled issue fact, formatted with original units and freshness notices."""

    label: str = Field(description="Fact label.")
    value: str = Field(description="Formatted value and freshness text, when applicable.")


class IpoSignal(Schema):
    """One scoring input in its original units and the normalized display scale."""

    name: str = Field(description="Signal label: GMP, Subscription, or News.")
    value: str = Field(description="Original value formatted with its units.")
    signal: str = Field(description="Normalized signed signal on the 1.0-10.0 scale.")


class IpoDetail(IpoSummary):
    """The issue facts and evidence behind the saved verdict."""

    facts: list[IpoFact] = Field(description="Issue facts, including metric freshness.")
    signals: list[IpoSignal] = Field(description="Usable saved scoring inputs.")
    notes: list[str] = Field(description="Saved explanation and missing-data notes.")
    scored_at: datetime | None = Field(description="Time the verdict was last calculated.")
    source_url: str = Field(description="Original source URL, or empty when unavailable.")


class MarketCount(Schema):
    """A group of evaluated predictions."""

    n: int = Field(description="Number of evaluated predictions.")
    correct: int = Field(description="Number that were right.")


class MarketStats(Schema):
    """Saved-result accuracy, using the existing evaluation rules."""

    total: int = Field(description="Evaluated predictions, excluding no-session days.")
    correct: int = Field(description="Predictions that were right.")
    accuracy: str = Field(description="Formatted accuracy percentage, or a dash.")
    baseline_direction: str | None = Field(description="Most common actual direction.")
    baseline_accuracy: str = Field(description="Formatted always-common-direction accuracy.")
    high_confidence: MarketCount = Field(description="Results with strength of at least 0.6.")
    recent: MarketCount = Field(description="Latest 30 evaluated results.")
    pending: int = Field(description="Predictions waiting for evaluation.")
    enough_results: bool = Field(description="Whether at least 30 results are available.")


class MarketQuote(Schema):
    """The latest saved close of a configured instrument."""

    name: str = Field(description="Configured instrument display name.")
    day: dt.date = Field(description="Exchange-local trading date of this saved close.")
    close: str = Field(description="Close formatted to two decimal places.")
    change: str = Field(description="Signed percentage change, or a dash when unavailable.")


class MarketPrediction(Schema):
    """A saved prediction and its result, without recalculating either."""

    date: dt.date = Field(description="Target trading day.")
    direction: str = Field(description="Predicted direction: up, down, or flat.")
    strength: str = Field(description="Signal strength on the 1.0-10.0 scale, not a probability.")
    actual_direction: str = Field(description="Actual direction, or empty while unavailable.")
    change: str = Field(description="Signed actual percentage change, or a dash.")
    result: Literal["Right", "Wrong", "No session", "Waiting"] = Field(
        description="Saved evaluation state."
    )


class Markets(Schema):
    """Track record, latest closes, and the newest 30 predictions."""

    stats: MarketStats = Field(description="Accuracy and baseline statistics.")
    quotes: list[MarketQuote] = Field(description="Latest closes in configured instrument order.")
    history: list[MarketPrediction] = Field(description="Newest 30 predictions, newest first.")


class TodayCue(Schema):
    """One of the five saved cues with the largest weighted contribution."""

    name: str
    change: str = Field(description="Signed percentage change, or a dash.")
    as_of: dt.date = Field(description="Saved cue trading date, not today's date.")


class TodayOutlook(Schema):
    """The latest saved prediction, with its actual target date and evidence."""

    date: dt.date
    direction: Literal["up", "down", "flat"]
    strength: str
    strength_label: str
    news_score: str
    news_articles: int
    global_score: str
    cues: list[TodayCue]
    notes: list[str]


class TodayMarkets(Schema):
    """Markets section; omitted entirely when Markets is unavailable."""

    outlook: TodayOutlook | None
    stats: MarketStats
    quotes: list[MarketQuote]


class TodayStory(Schema):
    """A bounded, deduplicated story from the existing 36-hour news selection."""

    title: str
    source: str
    url: str
    score: str
    reason: str
    companies: list[str]


class TodayNews(Schema):
    """Existing dashboard news counts and up to four stories per sentiment."""

    since: datetime
    articles: int
    positive: int
    negative: int
    good: list[TodayStory]
    bad: list[TodayStory]


class TodayIpo(Schema):
    """Existing dashboard issue facts, retaining original units and group ordering."""

    name: str
    category: str
    status: str
    open_date: dt.date | None
    close_date: dt.date | None
    price_band: str
    gmp: str
    subscribed: str
    verdict: str
    score: str | None


class TodayIpos(Schema):
    """Mutually exclusive dashboard groups, limited to four issues per group."""

    likely_good: list[TodayIpo]
    open_now: list[TodayIpo]
    upcoming: list[TodayIpo]
    days_ahead: int


class Today(Schema):
    """Feature-filtered daily overview; unavailable sections contain no data."""

    today: dt.date = Field(description="Current date in Asia/Kolkata.")
    markets: TodayMarkets | None
    news: TodayNews | None
    ipos: TodayIpos | None
    report: ReportSummary | None = Field(description="Latest report summary, without its text.")


class CompanyItem(Schema):
    """Company directory display fields, without scraped data or internal aliases."""

    id: int = Field(description="Company primary key.")
    name: str = Field(description="Company name, rendered as plain text.")
    symbol: str = Field(description="NSE or BSE symbol.")
    sector: str = Field(description="Sector, or empty when unknown.")
    screener_url: str = Field(description="Source URL; the browser only links HTTP(S) URLs.")
    last_updated: datetime | None = Field(description="Last data fetch, or null if never fetched.")


class CompanyPage(Schema):
    """A page of the company directory, ordered by name."""

    items: list[CompanyItem] = Field(description="Companies matching name, symbol, or sector.")
    page: int = Field(description="Resolved page number, starting at one.")
    pages: int = Field(description="Total pages; one when empty.")
    total: int = Field(description="Total matching companies.")
    page_size: int = Field(default=25, description="Resolved number of rows per page.")
    sectors: list[str] = Field(default_factory=list, description="All nonempty sectors, sorted.")


class DeliveryItem(ReportDelivery):
    """A send attempt associated with a report, or a test without a saved report."""

    report_date: dt.date | None = Field(description="Report date, or null when no report remains.")


class DeliveryPage(Schema):
    """The delivery overview, without chat IDs, recipients, or bot credentials."""

    chat_count: int = Field(description="Number of configured nonempty Telegram chat IDs.")
    items: list[DeliveryItem] = Field(description="Newest 50 send attempts, newest first.")
