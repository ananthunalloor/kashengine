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
