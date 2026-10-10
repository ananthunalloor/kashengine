"""The rules for each setting."""

import pytest

from apps.siteconfig import registry
from apps.siteconfig.registry import SPECS, validate


def test_every_setting_has_a_default_in_the_settings_file(settings):
    for key in SPECS:
        assert hasattr(settings, key), f"{key} has no default in config/settings/base.py"


def test_every_setting_is_in_a_known_group():
    assert {spec.group for spec in SPECS.values()} <= set(registry.GROUP_TITLES)
    for group in registry.GROUP_TITLES:
        assert registry.specs_in(group), f"The group {group} is empty."


def test_the_defaults_pass_the_rules_of_their_own_setting(settings):
    for key, spec in SPECS.items():
        value = getattr(settings, key)
        if spec.secret and not value:
            continue
        validate(spec, value)  # It must not raise.


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("LLM_TIMEOUT_SECONDS", "90", 90),
        ("LLM_TIMEOUT_SECONDS", 90.0, 90),
        ("PREDICTION_THRESHOLD", "0.2", 0.2),
        ("NEWS_SCRAPE_FULL_TEXT", "", False),
        ("NEWS_SCRAPE_FULL_TEXT", True, True),
        ("LLM_MODEL", "  llama3.2:3b ", "llama3.2:3b"),
        ("MARKET_CLOSE_TIME", "9:05", "09:05"),
        ("TELEGRAM_CHAT_IDS", "123\n-100456\n@mychannel", ["123", "-100456", "@mychannel"]),
        ("TELEGRAM_CHAT_IDS", "123, 456", ["123", "456"]),
        ("TELEGRAM_CHAT_IDS", "", []),
        (
            "IPO_SOURCE_URLS",
            "https://a.example/{month}/{year}\n",
            ["https://a.example/{month}/{year}"],
        ),
        ("LLM_BASE_URL", "http://ollama:11434", "http://ollama:11434"),
    ],
)
def test_good_values(key, value, expected):
    assert validate(SPECS[key], value) == expected


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("LLM_TIMEOUT_SECONDS", "abc"),
        ("LLM_TIMEOUT_SECONDS", "1"),  # Under the minimum.
        ("LLM_TIMEOUT_SECONDS", "999999"),  # Over the maximum.
        ("LLM_TIMEOUT_SECONDS", "10.5"),  # Not a whole number.
        ("PREDICTION_NEWS_WEIGHT", "1.5"),
        ("LLM_MODEL", "   "),  # Required.
        ("LLM_BASE_URL", "ollama:11434"),  # No scheme.
        ("LLM_BASE_URL", "javascript:alert(1)"),
        ("LLM_BASE_URL", "http://exa mple.com"),
        ("MARKET_CLOSE_TIME", "25:00"),
        ("MARKET_CLOSE_TIME", "noon"),
        ("TELEGRAM_CHAT_IDS", "not-a-chat"),
        ("TELEGRAM_CHAT_IDS", "123\nabc"),
        ("IPO_SOURCE_URLS", "ftp://example.com/x"),
    ],
)
def test_bad_values(key, value):
    with pytest.raises(ValueError, match=r"."):
        validate(SPECS[key], value)
