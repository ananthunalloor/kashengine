"""Private application contracts, independent of the public v1 API."""

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
