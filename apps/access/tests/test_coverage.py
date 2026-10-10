"""A guard: every web page has an access rule. A new page cannot skip the check by accident."""

from django.urls import URLPattern, URLResolver, get_resolver

from apps.access import features

# Pages that are not a feature. They are open to every signed-in user (login, logout, account),
# or they are the dashboard, which hides the parts of removed features itself.
NOT_FEATURES = features.OPEN_URL_NAMES | {"dashboard"}


def _web_url_names() -> set[str]:
    names: set[str] = set()
    for entry in get_resolver().url_patterns:
        if isinstance(entry, URLResolver) and entry.namespace == "web":
            names.update(p.name for p in entry.url_patterns if isinstance(p, URLPattern) and p.name)
    return names


def test_every_web_page_is_a_feature_or_on_the_open_list():
    names = _web_url_names()

    assert names, "No web URL found. The test is broken."
    unknown = names - NOT_FEATURES - set(features.BY_URL_NAME)
    assert not unknown, f"Add these pages to a feature in apps/access/features.py: {unknown}"


def test_every_feature_page_exists():
    names = _web_url_names()

    assert set(features.BY_URL_NAME) <= names


def test_the_feature_keys_are_short_and_unique():
    keys = [feature.key for feature in features.FEATURES]

    assert len(keys) == len(set(keys))
    assert all(len(key) <= 30 for key in keys)  # The column of FeatureBlock is 30 characters.
