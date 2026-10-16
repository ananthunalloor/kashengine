"""Build the read-only list of settings for the Config page, with the secrets hidden.

The view `views.config_view` calls `sections()`. The Settings index page in `views_settings.py`
also calls it (for the fixed settings), and calls `display_value()` for each setting row. The
module reads the Django settings object. For a setting that the dashboard manages, it uses the
value from `apps.siteconfig.conf` (the saved dashboard value, or else the environment value).

Security: a setting is a secret when its name matches `SECRET_NAME`. The module never returns
the value of a secret. It returns only "set (hidden)" or "not set". It also hides the login
part of a URL, and it shows only the number of Telegram chat ids.
"""

import re
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings

from apps.siteconfig import conf, registry

SECRET_NAME = re.compile(
    r"SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|ENCRYPTION_KEY|PRIVATE", re.IGNORECASE
)
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
    """Hide the user name and the password of a URL like `redis://:pw@host/0`.

    A URL that has no login part is returned as it is. For a URL with a login part, the function
    replaces the user name and the password with the text `<hidden>`. It keeps the scheme, the
    host, the port, the path, and the query. It removes the fragment. The host is in lower case.

    Args:
        value: The text of a URL, or any other string.

    Returns:
        The text with the login part hidden, or `value` itself if it has no login part.
    """
    if not URL_WITH_LOGIN.match(value):
        return value
    parts = urlsplit(value)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, f"<hidden>@{host}", parts.path, parts.query, ""))


def display_value(name: str, value: object) -> str:
    """Return the text that the pages show for one setting.

    The rules run in this order. A name that matches `SECRET_NAME` gives "set (hidden)" for a
    value that is not empty, and "not set" for an empty value. `TELEGRAM_CHAT_IDS` gives the
    number of chat ids, for example "2 chat(s)". A string goes through `mask_url`, and an empty
    string gives "not set". A list or a tuple gives its items joined with commas, and an empty
    list gives "not set". Any other value (a number, a boolean) gives `str(value)`.

    Args:
        name: The name of the setting, for example `CELERY_BROKER_URL`.
        value: The value of the setting. It can be of any type.

    Returns:
        The text to show. It never holds the value of a secret.

    Security:
        The check of the name decides if a value is a secret. A new secret setting must have a
        name that matches `SECRET_NAME`. The items of a list are not passed through `mask_url`.
    """
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
    """Return the engine, the host, and the name of the default database.

    The text has the form "engine, host, name". The engine is the last part of the `ENGINE` path,
    for example `postgresql`. The text "local file" replaces an empty host. The function reads
    only the `default` entry of `DATABASES`.

    Returns:
        The summary text. It never holds the user name or the password.
    """
    config = settings.DATABASES["default"]
    engine = str(config.get("ENGINE", "")).rsplit(".", 1)[-1]
    host = config.get("HOST") or "local file"
    return f"{engine}, {host}, {config.get('NAME')}"


def _effective(name: str) -> object:
    """Return the value that the application uses for a setting now.

    A setting that is in the registry of the dashboard goes through `conf.get`. That call returns
    the saved dashboard value, or else the environment value. Any other setting comes from the
    Django settings object.

    Args:
        name: The name of the setting. It must exist in the Django settings.

    Returns:
        The raw value. It can hold a secret, so the caller must pass it through `display_value`.

    Raises:
        AttributeError: If the setting does not exist (from `getattr`).
    """
    return conf.get(name) if name in registry.SPECS else getattr(settings, name)


def sections() -> list[tuple[str, list[tuple[str, str]]]]:
    """Return all settings of the Config page, in groups.

    The function reads every upper-case name of the Django settings. It sorts the names, and it
    puts each name in the group of `GROUPS` that has a matching prefix. A prefix that ends with an
    underscore matches the start of a name. Any other prefix must match the whole name. A name
    that matches no group does not appear. The "Environment" group also gets a `DATABASE` row
    at its end. The function leaves out a group that has no rows.

    Returns:
        A list of pairs `(group title, rows)`. Each row is a pair `(name, text)`. The text comes
        from `display_value`, so a secret is hidden. The groups keep the order of `GROUPS`.
    """
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
