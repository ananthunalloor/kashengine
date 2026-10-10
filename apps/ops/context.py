"""Template context for the Ops pages."""

from django.urls import reverse

SECTIONS = (
    ("overview", "Overview", "ops:overview"),
    ("jobs", "Jobs", "ops:jobs"),
    ("runs", "Runs", "ops:runs"),
    ("logs", "Logs", "ops:logs"),
    ("metrics", "Metrics", "ops:metrics"),
    ("users", "Users", "ops:users"),
    ("logins", "Logins", "ops:logins"),
    ("audit", "Audit", "ops:audit"),
    ("settings", "Settings", "ops:settings"),
    ("schedule", "Schedule", "ops:schedule"),
    ("feeds", "Feeds", "ops:feeds"),
    ("instruments", "Instruments", "ops:instruments"),
    ("config", "Config", "ops:config"),
)


def ops_nav(request) -> dict:
    """The menu of the Ops pages. Only the Ops pages need it."""
    match = getattr(request, "resolver_match", None)
    if not match or match.namespace != "ops":
        return {}
    return {"ops_sections": [(key, label, reverse(name)) for key, label, name in SECTIONS]}
