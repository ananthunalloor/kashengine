"""The settings that the config page shows, with the secrets hidden."""

import re
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings

from apps.siteconfig import conf, registry

SECRET_NAME = re.compile(r"SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|PRIVATE", re.IGNORECASE)
URL_WITH_LOGIN = re.compile(r"^[a-z][a-z0-9+.-]*://[^/@\s]+@", re.IGNORECASE)

GROUPS = (
    ("Environment", ("DEBUG", "TIME_ZONE", "ALLOWED_HOSTS", "CSRF_TRUSTED_ORIGINS")),
    ("Security", ("SECURE_", "SESSION_COOKIE_", "CSRF_COOKIE_")),
    ("Queue", ("CELERY_BROKER_URL", "CELERY_TIMEZONE")),
    ("LLM", ("LLM_",)),
    ("News", ("NEWS_", "SENTIMENT_")),
    ("Markets", ("MARKET_", "PREDICTION_")),
    ("Companies", ("SCREENER_",)),
    ("IPOs", ("IPO_",)),
    ("Telegram and report", ("TELEGRAM_", "REPORT_")),
    ("Web and ops", ("DATASTAR_SRC", "WEB_PAGE_SIZE", "OPS_", "LOG_FILE")),
)
HIDDEN_TEXT = "set (hidden)"
EMPTY_TEXT = "not set"


def mask_url(value: str) -> str:
    """Hide the user name and the password of a URL like redis://:pw@host/0."""
    if not URL_WITH_LOGIN.match(value):
        return value
    parts = urlsplit(value)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, f"<hidden>@{host}", parts.path, parts.query, ""))


def display_value(name: str, value: object) -> str:
    """The text to show for a setting. A secret is never shown."""
    if SECRET_NAME.search(name):
        return HIDDEN_TEXT if value else EMPTY_TEXT
    if name == "TELEGRAM_CHAT_IDS":
        return f"{len(value)} chat(s)" if isinstance(value, list | tuple) else str(value)
    if isinstance(value, str):
        return mask_url(value) or EMPTY_TEXT
    if isinstance(value, list | tuple):
        return ", ".join(str(item) for item in value) or EMPTY_TEXT
    return str(value)


def database_summary() -> str:
    """The database engine, host, and name. Never the password."""
    config = settings.DATABASES["default"]
    engine = str(config.get("ENGINE", "")).rsplit(".", 1)[-1]
    host = config.get("HOST") or "local file"
    return f"{engine}, {host}, {config.get('NAME')}"


def _effective(name: str) -> object:
    """The value in use: the dashboard value if there is one, else the environment value."""
    return conf.get(name) if name in registry.SPECS else getattr(settings, name)


def sections() -> list[tuple[str, list[tuple[str, str]]]]:
    """The settings, in groups. Each item is (name, text)."""
    names = sorted(name for name in dir(settings) if name.isupper())
    result = []
    for title, prefixes in GROUPS:
        rows = [
            (name, display_value(name, _effective(name)))
            for name in names
            if any(
                name == prefix or (prefix.endswith("_") and name.startswith(prefix))
                for prefix in prefixes
            )
        ]
        if title == "Environment":
            rows.append(("DATABASE", database_summary()))
        if rows:
            result.append((title, rows))
    return result
