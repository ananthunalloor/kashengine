"""Small helpers for Datastar requests.

Datastar sends its signals (the values of the filter fields) in a query parameter named
"datastar", as JSON. A page that is loaded without Datastar uses plain query parameters. These
helpers read both, so a filter page works with and without JavaScript.

The answer to a Datastar request is a piece of HTML. Datastar puts its elements in the page by
id. No streaming is needed, so it works with the normal Gunicorn workers.
"""

import json
from urllib.parse import urlencode

MAX_VALUE_CHARS = 100


def is_datastar(request) -> bool:
    """Return True if the request comes from Datastar."""
    return request.headers.get("Datastar-Request") == "true"


def read_filters(request, names: tuple[str, ...]) -> dict[str, str]:
    """The values of the named filters, as short plain text. A missing value is "" ."""
    raw = request.GET.get("datastar")
    source: dict = {}
    if raw:
        try:
            loaded = json.loads(raw)
        except ValueError:
            loaded = {}
        source = loaded if isinstance(loaded, dict) else {}
    else:
        source = request.GET
    values = {}
    for name in names:
        value = source.get(name, "")
        values[name] = ("" if value is None else str(value)).strip()[:MAX_VALUE_CHARS]
    return values


def read_page(filters: dict[str, str]) -> int:
    """The page number from the filters. A bad value gives page 1."""
    try:
        return max(1, int(filters.get("page") or 1))
    except ValueError:
        return 1


def querystring(filters: dict[str, str], exclude: tuple[str, ...] = ("page",)) -> str:
    """The filters as a query string, without empty values. For links that work without JS."""
    return urlencode({k: v for k, v in filters.items() if v and k not in exclude})


def signals_json(filters: dict[str, str]) -> str:
    """The filters as the starting signals of a page. Every filter has a signal."""
    return json.dumps({**filters, "page": filters.get("page") or "1"})
