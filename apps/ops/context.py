"""Template context for the Ops pages.

The function `ops_nav` is a Django context processor. The `TEMPLATES` setting in
`config/settings/base.py` lists it as `apps.ops.context.ops_nav`. The base template of the Ops
pages uses its result to draw the menu. Each key in `SECTIONS` is the same text as the
`section` value that a view puts in its template context. The template uses it to mark the
page that is open.
"""

from django.urls import reverse

SECTIONS = (
    ("overview", "Overview", "ops:overview"),
    ("jobs", "Jobs", "ops:jobs"),
    ("runs", "Runs", "ops:runs"),
    ("logs", "Logs", "ops:logs"),
    ("metrics", "Metrics", "ops:metrics"),
    ("users", "Users", "ops:users"),
    ("invites", "Invite codes", "ops:invites"),
    ("subscriptions", "Subscriptions", "ops:subscriptions"),
    ("logins", "Logins", "ops:logins"),
    ("audit", "Audit", "ops:audit"),
    ("settings", "Settings", "ops:settings"),
    ("schedule", "Schedule", "ops:schedule"),
    ("feeds", "Feeds", "ops:feeds"),
    ("instruments", "Instruments", "ops:instruments"),
    ("config", "Config", "ops:config"),
)


def ops_nav(request) -> dict:
    """Return the menu of the Ops pages for the template context.

    The function works only for a request that resolved to a URL in the `ops` namespace. For any
    other request, and for a request that has no `resolver_match` yet (for example a 404 page),
    it returns an empty dictionary.

    Args:
        request: The current HTTP request.

    Returns:
        A dictionary with the key `ops_sections`. Its value is a list of tuples
        `(key, label, url)` in the order of `SECTIONS`. The dictionary is empty outside the Ops
        pages.
    """
    match = getattr(request, "resolver_match", None)
    if not match or match.namespace != "ops":
        return {}
    sections = [(key, label, reverse(name)) for key, label, name in SECTIONS]
    if request.user.is_superuser:
        sections.append(("backups", "Backups", reverse("ops:backups")))
    return {"ops_sections": sections}
