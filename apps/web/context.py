"""Template context for every page of the web app."""

from django.urls import reverse

from apps.access.middleware import access_for
from apps.siteconfig import conf

# (label, url name, the url names that belong to the section, the feature or None)
SECTIONS = (
    ("Today", "web:dashboard", {"dashboard"}, None),
    ("Reports", "web:reports", {"reports", "report"}, "reports"),
    ("News", "web:news", {"news"}, "news"),
    ("IPOs", "web:ipos", {"ipos", "ipo"}, "ipos"),
    ("Markets", "web:markets", {"markets"}, "markets"),
    ("Companies", "web:companies", {"companies"}, "companies"),
    ("Delivery", "web:delivery", {"delivery"}, "delivery"),
)


def web_settings(request) -> dict:
    """Values that every template needs: the Datastar script and the main menu."""
    match = getattr(request, "resolver_match", None)
    current = match.url_name if match and match.namespace == "web" else None
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"datastar_src": conf.DATASTAR_SRC, "nav": [], "features": frozenset(), "notice": ""}
    access = access_for(request)
    nav = [
        {"label": label, "url": reverse(name), "active": current in names}
        for label, name, names, feature in SECTIONS
        if access.subscription_ok and (feature is None or access.can(feature))
    ]
    nav.append({"label": "Account", "url": reverse("web:account"), "active": current == "account"})
    if user.is_staff:
        in_ops = bool(match and match.namespace == "ops")
        nav.append({"label": "Ops", "url": reverse("ops:overview"), "active": in_ops})
    return {
        "datastar_src": conf.DATASTAR_SRC,
        "nav": nav,
        "features": access.allowed,
        "notice": access.notice(),
    }
