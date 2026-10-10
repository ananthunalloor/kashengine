"""The features that an admin can switch on or off for a user.

A feature is a part of the web app. Every user has all features by default. An admin removes
a feature from one user on Ops > Users. The middleware checks the feature of each page by the
name of its URL, so a new page cannot skip the check if its name is in this list.

The pages "Today" (dashboard), the account page, login, and logout are not features. Everybody
who may use the site can open them. The dashboard hides the parts that belong to a feature that
the user does not have.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    """One feature: its key, its name, and the URL names of its pages."""

    key: str
    label: str
    help: str
    url_names: frozenset[str]


FEATURES: tuple[Feature, ...] = (
    Feature(
        "reports",
        "Daily reports",
        "The list of daily reports and each report.",
        frozenset({"reports", "report"}),
    ),
    Feature("news", "News", "The scored news list.", frozenset({"news"})),
    Feature("ipos", "IPOs", "The IPO list, the scores, and each IPO.", frozenset({"ipos", "ipo"})),
    Feature(
        "markets",
        "Markets and outlook",
        "The prediction, its history and accuracy, and the quotes. The outlook on Today.",
        frozenset({"markets"}),
    ),
    Feature("companies", "Companies", "The company list.", frozenset({"companies"})),
    Feature(
        "delivery",
        "Delivery",
        "The page with the Telegram send attempts.",
        frozenset({"delivery"}),
    ),
)

BY_KEY: dict[str, Feature] = {feature.key: feature for feature in FEATURES}
KEYS: frozenset[str] = frozenset(BY_KEY)
BY_URL_NAME: dict[str, Feature] = {
    name: feature for feature in FEATURES for name in feature.url_names
}

# Pages that every signed-in user can open, also without a subscription.
OPEN_URL_NAMES: frozenset[str] = frozenset({"login", "logout", "account"})
