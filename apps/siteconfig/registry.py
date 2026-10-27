"""The settings that an admin can change on the dashboard.

This file describes each setting: its type, its limits, its group, and its help text. It does
not hold the values. The value of a setting is, in this order:

1. the value that an admin saved on the dashboard (the database),
2. the environment variable, or the default in config/settings/base.py.

A few settings cannot change while the server runs (the database URL, the Redis URL, the secret
key, the allowed hosts). They stay in the environment and are not in this list.
"""

import re
from dataclasses import dataclass
from datetime import time
from typing import Any

INT, FLOAT, BOOL, STR, URL, URLS, LIST, SECRET, CLOCK = (
    "int",
    "float",
    "bool",
    "str",
    "url",
    "urls",
    "list",
    "secret",
    "clock",
)

URL_PATTERN = re.compile(r"^https?://[^\s/?#]+(?:[/?#]\S*)?$")
CLOCK_PATTERN = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


@dataclass(frozen=True)
class Spec:
    """One setting."""

    key: str
    label: str
    kind: str
    group: str
    help: str = ""
    minimum: float | None = None
    maximum: float | None = None
    item_pattern: str = ""  # For a list: each item must match this pattern.
    item_hint: str = ""  # What an item looks like. It is the error text.
    required: bool = False

    @property
    def secret(self) -> bool:
        """True if the value is encrypted and never shown."""
        return self.kind == SECRET


GROUPS: tuple[tuple[str, str, str], ...] = (
    ("telegram", "Telegram", "The bot that sends the daily report."),
    ("report", "Report", "What the daily report contains."),
    ("llm", "LLM server", "The local model that scores the news."),
    ("news", "News collection", "How the news is downloaded."),
    ("sentiment", "Sentiment scoring", "How the articles are scored."),
    ("markets", "Markets and prediction", "The market time, and how the prediction is made."),
    ("ipos", "IPOs", "The IPO sources and the scoring rules."),
    ("companies", "Company data", "Data from Screener.in."),
    (
        "subscription",
        "Subscription",
        "The trial, the paid period, and the rule that locks users out without a subscription.",
    ),
    ("api", "REST API", "The /api/v1/ API: switch, limits, paging, and tokens."),
    ("security", "Login security", "Limits on failed logins (django-axes)."),
    ("web", "Web and ops", "Pages, history, and logs."),
)
GROUP_TITLES = {key: title for key, title, _help in GROUPS}

_SPECS: tuple[Spec, ...] = (
    Spec(
        "UPSTOX_ENABLED",
        "Enable Upstox",
        BOOL,
        "markets",
        "Opt-in stored company quotes, fundamentals, news and IPO ingestion. "
        "Existing sources remain enabled independently.",
    ),
    Spec(
        "UPSTOX_ACCESS_TOKEN",
        "Upstox access token",
        SECRET,
        "markets",
        "Server-side bearer token. Renew when it expires; never enter it in a browser URL.",
    ),
    Spec(
        "UPSTOX_FUNDAMENTALS_DAYS",
        "Upstox fundamentals refresh (days)",
        INT,
        "markets",
        "Keep successful snapshots for reuse and refresh only when due.",
        minimum=1,
        maximum=365,
    ),
    Spec(
        "UPSTOX_STREAM_INDICES",
        "Upstox live indices",
        LIST,
        "markets",
        "One Upstox index instrument key for each line, for example NSE_INDEX|Nifty 50. "
        "The stream worker follows them for the live dashboard; restart it after a change.",
        item_pattern=r"^(NSE|BSE)_INDEX\|[A-Za-z0-9 &.\-]{1,60}$",
        item_hint="an index key like NSE_INDEX|Nifty 50",
    ),
    # Telegram
    Spec(
        "TELEGRAM_BOT_TOKEN",
        "Bot token",
        SECRET,
        "telegram",
        "From @BotFather. It is saved encrypted and never shown again.",
    ),
    Spec(
        "TELEGRAM_CHAT_IDS",
        "Chat IDs",
        LIST,
        "telegram",
        "One chat ID for each line. A person, a group (starts with -), or @channelname. "
        "Run the job 'Check the Telegram bot' to find the IDs.",
        item_pattern=r"^(-?\d{1,20}|@[A-Za-z][A-Za-z0-9_]{4,31})$",
        item_hint="a chat ID like 123456789 or -1001234567890, or @channelname",
    ),
    Spec(
        "TELEGRAM_API_URL",
        "API address",
        URL,
        "telegram",
        "Change it only if you run your own Bot API server.",
        required=True,
    ),
    Spec("TELEGRAM_TIMEOUT_SECONDS", "Timeout (seconds)", INT, "telegram", minimum=3, maximum=300),
    # Report
    Spec(
        "REPORT_NEWS_ITEMS", "News items", INT, "report", "For good news, and for bad news.", 1, 20
    ),
    Spec(
        "REPORT_NEWS_MIN_RELEVANCE",
        "Minimum relevance of a news item",
        FLOAT,
        "report",
        "From 0 to 1.",
        0,
        1,
    ),
    Spec("REPORT_IPO_ITEMS", "IPO items", INT, "report", "For each IPO list.", 1, 30),
    Spec("REPORT_IPO_DAYS_AHEAD", "IPO days ahead", INT, "report", "Look this far ahead.", 1, 60),
    # LLM
    Spec(
        "LLM_BASE_URL",
        "Server address",
        URL,
        "llm",
        "Ollama, for example http://ollama:11434.",
        required=True,
    ),
    Spec("LLM_MODEL", "Model", STR, "llm", "The model name on the server.", required=True),
    Spec(
        "LLM_TIMEOUT_SECONDS",
        "Timeout (seconds)",
        INT,
        "llm",
        "A small model on a CPU can need a minute for one answer.",
        5,
        3600,
    ),
    # News
    Spec(
        "NEWS_USER_AGENT",
        "User agent",
        STR,
        "news",
        "It names our bot and gives a contact link. Do not make it look like a browser.",
        required=True,
    ),
    Spec("NEWS_REQUEST_TIMEOUT", "Request timeout (seconds)", INT, "news", minimum=3, maximum=300),
    Spec("NEWS_SCRAPE_FULL_TEXT", "Download the full article text", BOOL, "news"),
    Spec(
        "NEWS_SCRAPE_DELAY_SECONDS",
        "Wait between requests to a site (seconds)",
        FLOAT,
        "news",
        minimum=0,
        maximum=60,
    ),
    Spec(
        "NEWS_SCRAPE_BATCH_SIZE",
        "Articles for each scrape run",
        INT,
        "news",
        minimum=1,
        maximum=1000,
    ),
    Spec(
        "NEWS_SCRAPE_MAX_AGE_HOURS",
        "Do not scrape articles older than (hours)",
        INT,
        "news",
        minimum=1,
        maximum=720,
    ),
    Spec(
        "NEWS_STALE_AFTER_HOURS",
        "Warn when no new article for (hours)",
        INT,
        "news",
        "The Overview page shows a warning.",
        1,
        168,
    ),
    # Sentiment
    Spec(
        "SENTIMENT_MAX_CHARS",
        "Article text for the model (characters)",
        INT,
        "sentiment",
        minimum=200,
        maximum=20000,
    ),
    Spec(
        "SENTIMENT_BATCH_SIZE", "Articles for each run", INT, "sentiment", minimum=1, maximum=1000
    ),
    Spec(
        "SENTIMENT_MAX_AGE_HOURS",
        "Do not score articles older than (hours)",
        INT,
        "sentiment",
        minimum=1,
        maximum=720,
    ),
    Spec("SENTIMENT_MAX_ATTEMPTS", "Tries for an article", INT, "sentiment", minimum=1, maximum=10),
    # Markets
    Spec(
        "MARKET_CLOSE_TIME",
        "Market close time (HH:MM)",
        CLOCK,
        "markets",
        "In the time zone of the server (IST).",
        required=True,
    ),
    Spec(
        "MARKET_FINAL_BUFFER_MINUTES",
        "Wait after the close for the final price (minutes)",
        INT,
        "markets",
        minimum=0,
        maximum=240,
    ),
    Spec(
        "MARKET_FLAT_BAND_PCT",
        "A day is flat if it moves less than (%)",
        FLOAT,
        "markets",
        minimum=0,
        maximum=5,
    ),
    Spec(
        "PREDICTION_NEWS_WEIGHT",
        "Weight of the news in the score",
        FLOAT,
        "markets",
        "From 0 to 1. The rest is the global cues.",
        0,
        1,
    ),
    Spec(
        "PREDICTION_THRESHOLD",
        "Score for up or down",
        FLOAT,
        "markets",
        "A score closer to zero than this is flat.",
        0,
        1,
    ),
    Spec(
        "PREDICTION_MIN_ARTICLES",
        "Articles that the news signal needs",
        INT,
        "markets",
        minimum=0,
        maximum=1000,
    ),
    # IPOs
    Spec(
        "IPO_FETCH_ENABLED",
        "Read the IPO list",
        BOOL,
        "ipos",
        "See the note in apps/ipos/sources.py.",
    ),
    Spec(
        "IPO_SOURCE_URLS",
        "IPO list addresses",
        URLS,
        "ipos",
        "One address for each line. An address can have {month}, {year}, and {fy}.",
    ),
    Spec(
        "IPO_GMP_ENABLED",
        "Read the GMP and the subscription",
        BOOL,
        "ipos",
        "See the note in apps/ipos/gmp.py.",
    ),
    Spec("IPO_GMP_URL", "GMP address", URL, "ipos", required=True),
    Spec("IPO_LISTING_ENABLED", "Read the listing prices (Yahoo Finance)", BOOL, "ipos"),
    Spec(
        "IPO_LISTING_CHECK_DAYS",
        "Listing check: days to look back",
        INT,
        "ipos",
        minimum=1,
        maximum=90,
    ),
    Spec(
        "IPO_KEEP_DAYS",
        "Skip new IPOs that opened more than (days) ago",
        INT,
        "ipos",
        minimum=1,
        maximum=365,
    ),
    Spec(
        "IPO_METRIC_MAX_AGE_HOURS",
        "GMP and subscription count for (hours)",
        INT,
        "ipos",
        minimum=1,
        maximum=720,
    ),
    Spec("IPO_NEWS_DAYS", "News window for an IPO (days)", INT, "ipos", minimum=1, maximum=90),
    Spec("IPO_GOOD_SCORE", "A score from this up is good", FLOAT, "ipos", minimum=-1, maximum=1),
    Spec("IPO_WEAK_SCORE", "A score under this is weak", FLOAT, "ipos", minimum=-1, maximum=1),
    Spec(
        "IPO_GOOD_GAIN_PCT",
        "A listing gain from this up did well (%)",
        FLOAT,
        "ipos",
        minimum=0,
        maximum=500,
    ),
    # Companies
    Spec(
        "SCREENER_ENABLED",
        "Read Screener.in",
        BOOL,
        "companies",
        "Read their terms first (apps/companies/screener.py).",
    ),
    Spec("SCREENER_BASE_URL", "Screener.in address", URL, "companies", required=True),
    Spec(
        "SCREENER_DELAY_SECONDS",
        "Wait between requests (seconds)",
        FLOAT,
        "companies",
        minimum=0,
        maximum=120,
    ),
    Spec(
        "SCREENER_REFRESH_DAYS",
        "Read a company again after (days)",
        INT,
        "companies",
        minimum=1,
        maximum=365,
    ),
    Spec(
        "SCREENER_BATCH_SIZE", "Companies for each run", INT, "companies", minimum=1, maximum=1000
    ),
    # Security
    Spec(
        "LOGIN_FAILURE_LIMIT",
        "Failed logins before a lockout",
        INT,
        "security",
        "Counted for each address, and for each address with the same user name.",
        1,
        100,
    ),
    Spec(
        "LOGIN_COOLOFF_MINUTES",
        "Lockout time (minutes)",
        INT,
        "security",
        "After this time the address can try again. 0 locks it until an admin unlocks it.",
        0,
        100_000,
    ),
    # Subscription
    Spec(
        "SUBSCRIPTIONS_REQUIRED",
        "Require a subscription",
        BOOL,
        "subscription",
        "Off: nobody is locked out. On: a user needs an active trial or subscription. "
        "Staff and superusers always have access.",
    ),
    Spec(
        "SUBSCRIPTION_TRIAL_DAYS",
        "Trial for a new user (days)",
        INT,
        "subscription",
        "A new user gets this trial. It does not change trials that already started.",
        0,
        365,
    ),
    Spec(
        "SUBSCRIPTION_PERIOD_DAYS",
        "One paid period (days)",
        INT,
        "subscription",
        "The default number of days when an admin gives a subscription.",
        1,
        366,
    ),
    Spec(
        "SUBSCRIPTION_PRICE",
        "Price for one period",
        FLOAT,
        "subscription",
        "Shown on the account page. 0 hides the price. There is no payment step yet.",
        0,
        1_000_000,
    ),
    Spec(
        "SUBSCRIPTION_CURRENCY",
        "Currency",
        STR,
        "subscription",
        "The code that is shown after the price, for example INR.",
        required=True,
    ),
    Spec(
        "SUBSCRIPTION_NOTICE_DAYS",
        "Show the 'ends soon' notice (days before the end)",
        INT,
        "subscription",
        "A user sees a notice in the menu this many days before the trial or subscription ends.",
        1,
        60,
    ),
    Spec(
        "SUBSCRIPTION_CONTACT_TEXT",
        "Text for a user who needs a subscription",
        STR,
        "subscription",
        "Shown on the account page. For example how to pay or whom to ask.",
        required=True,
    ),
    # REST API
    Spec(
        "API_ENABLED",
        "REST API on",
        BOOL,
        "api",
        "If off, every /api/ address answers 503. Web pages do not change.",
    ),
    Spec(
        "API_DOCS_ENABLED",
        "Swagger page on",
        BOOL,
        "api",
        "The interactive page at /api/v1/docs. It needs a login. The OpenAPI file stays on.",
    ),
    Spec(
        "API_RATE_LIMIT_PER_MINUTE",
        "Requests a minute for each token or user",
        INT,
        "api",
        "The limit in each minute window. A client over the limit gets 429 and Retry-After.",
        1,
        100_000,
    ),
    Spec(
        "API_AUTH_FAIL_LIMIT_PER_MINUTE",
        "Failed token checks a minute for each address",
        INT,
        "api",
        "A client address over this limit gets 429 for the rest of the minute.",
        1,
        10_000,
    ),
    Spec("API_PAGE_SIZE", "Default rows on an API page", INT, "api", minimum=1, maximum=500),
    Spec(
        "API_PAGE_SIZE_MAX",
        "Most rows on an API page",
        INT,
        "api",
        "A request for more rows gets 422.",
        1,
        500,
    ),
    Spec(
        "API_TOKEN_MAX_PER_USER",
        "Active tokens for each user",
        INT,
        "api",
        "A user must revoke a token before making a new one over this limit.",
        1,
        100,
    ),
    Spec(
        "API_TOKEN_EXPIRY_DAYS",
        "New token lifetime (days)",
        INT,
        "api",
        "0 means a new token does not expire. Existing tokens keep their end date.",
        0,
        3650,
    ),
    # Web and ops
    Spec(
        "DATASTAR_SRC",
        "Datastar script address",
        STR,
        "web",
        "To serve it from this site, use /static/vendor/datastar.js. "
        "If you use another host, allow it in the Content-Security-Policy (Caddyfile).",
        required=True,
    ),
    Spec("WEB_PAGE_SIZE", "Rows on a page of the web app", INT, "web", minimum=5, maximum=200),
    Spec("OPS_PAGE_SIZE", "Rows on a page of the Ops lists", INT, "web", minimum=5, maximum=500),
    Spec(
        "OPS_RETENTION_DAYS",
        "Keep task runs and login events (days)",
        INT,
        "web",
        minimum=1,
        maximum=3650,
    ),
    Spec(
        "OPS_LOG_TAIL_BYTES",
        "Log viewer: bytes to read",
        INT,
        "web",
        minimum=10_000,
        maximum=50_000_000,
    ),
)

SPECS: dict[str, Spec] = {spec.key: spec for spec in _SPECS}


def specs_in(group: str) -> list[Spec]:
    """Return the settings of one group, in the order of this file.

    Args:
        group: The name of the group, for example `news`.

    Returns:
        The specs of the group. The list is empty for an unknown group.
    """
    return [spec for spec in _SPECS if spec.group == group]


def clean_clock(value: str) -> time:
    """Parse HH:MM. Raise ValueError for a bad text.

    Args:
        value: The text, for example `15:30`.

    Returns:
        The time of day, without a time zone.

    Raises:
        ValueError: If the text does not have the form HH:MM or the hour or minute is wrong.
    """
    match = CLOCK_PATTERN.match(value.strip())
    if not match:
        msg = "Use the form HH:MM, for example 15:30."
        raise ValueError(msg)
    return time(int(match[1]), int(match[2]))


def validate(spec: Spec, value: Any) -> Any:  # noqa: C901, PLR0912
    """Check a value against its spec and return the clean value. Raise ValueError if bad.

    The rules depend on the kind of the spec. A number must be in the range of the spec. A
    text is trimmed. A required text must not be empty. A URL must start with `http://` or
    `https://`. A clock text must have the form HH:MM and the result has two digits for the hour.
    A list can be a list or a text that is split at commas and new lines. Each item must match
    the pattern of the spec.

    Args:
        spec: The spec of the setting.
        value: The raw value, for example from a form or from saved JSON.

    Returns:
        The clean value: a bool, an int or float, a text, or a list of texts.

    Raises:
        ValueError: If the value is not valid. The message is safe to show to the admin.
    """
    kind = spec.kind
    if kind == BOOL:
        return bool(value)
    if kind in {INT, FLOAT}:
        try:
            number = int(value) if kind == INT and not isinstance(value, float) else float(value)
        except (TypeError, ValueError):
            msg = "Enter a number."
            raise ValueError(msg) from None
        if kind == INT and number != int(number):
            msg = "Enter a whole number."
            raise ValueError(msg)
        number = int(number) if kind == INT else number
        if spec.minimum is not None and number < spec.minimum:
            msg = f"The smallest value is {spec.minimum:g}."
            raise ValueError(msg)
        if spec.maximum is not None and number > spec.maximum:
            msg = f"The largest value is {spec.maximum:g}."
            raise ValueError(msg)
        return number
    if kind in {STR, URL, SECRET, CLOCK}:
        text = str(value).strip()
        if not text:
            if spec.required:
                msg = "This value is required."
                raise ValueError(msg)
            return ""
        if kind == URL and not URL_PATTERN.match(text):
            msg = "Enter an address that starts with http:// or https://."
            raise ValueError(msg)
        if kind == CLOCK:
            parsed = clean_clock(text)
            return f"{parsed.hour:02d}:{parsed.minute:02d}"
        return text
    if kind in {LIST, URLS}:
        items = value if isinstance(value, list | tuple) else re.split(r"[\n,]+", str(value))
        items = [str(item).strip() for item in items if str(item).strip()]
        for item in items:
            if kind == URLS and not URL_PATTERN.match(item):
                msg = f"Not an address that starts with http:// or https://: {item}"
                raise ValueError(msg)
            if kind == LIST and spec.item_pattern and not re.match(spec.item_pattern, item):
                msg = f"'{item}' is not valid. Use {spec.item_hint}."
                raise ValueError(msg)
        return items
    msg = f"Unknown kind: {kind}"
    raise ValueError(msg)
