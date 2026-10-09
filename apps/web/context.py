"""Template context for every page of the web app."""

from django.conf import settings
from django.urls import reverse

# (label, url name, the url names that belong to the section)
SECTIONS = (
    ("Today", "web:dashboard", {"dashboard"}),
    ("Reports", "web:reports", {"reports", "report"}),
    ("News", "web:news", {"news"}),
    ("IPOs", "web:ipos", {"ipos", "ipo"}),
    ("Markets", "web:markets", {"markets"}),
    ("Companies", "web:companies", {"companies"}),
    ("Delivery", "web:delivery", {"delivery"}),
)


def web_settings(request) -> dict:
    """Values that every template needs: the Datastar script and the main menu."""
    match = getattr(request, "resolver_match", None)
    current = match.url_name if match and match.namespace == "web" else None
    nav = [
        {"label": label, "url": reverse(name), "active": current in names}
        for label, name, names in SECTIONS
    ]
    user = getattr(request, "user", None)
    if user is not None and user.is_staff:
        in_ops = bool(match and match.namespace == "ops")
        nav.append({"label": "Ops", "url": reverse("ops:overview"), "active": in_ops})
    return {"datastar_src": settings.DATASTAR_SRC, "nav": nav}
