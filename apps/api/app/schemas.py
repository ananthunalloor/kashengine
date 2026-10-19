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
