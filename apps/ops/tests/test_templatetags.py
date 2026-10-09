"""The template filters and the bar chart."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.ops.templatetags import ops_extras as x


@pytest.mark.parametrize(
    ("ms", "text"),
    [(None, "–"), ("", "–"), (0, "0 ms"), (850, "850 ms"), (1200, "1.2 s"), (184000, "3 min 4 s")],
)
def test_duration(ms, text):
    assert x.duration(ms) == text


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(None, "–"), (30, "30 s"), (300, "5 min"), (3 * 3600, "3 h"), (2 * 86400, "2 days")],
)
def test_span(seconds, text):
    assert x.span(seconds) == text


def test_ago_and_until():
    now = timezone.now()

    assert x.ago(None) == "–"
    assert x.ago(now - timedelta(minutes=5, seconds=2)) == "5 min ago"
    assert x.ago(now + timedelta(minutes=5)) == "0 s ago"  # A moment in the future is not negative.
    assert x.until(now - timedelta(minutes=1)) == "now"
    assert x.until(now + timedelta(hours=3, minutes=1)) == "in 3 h"
    assert x.until(None) == "–"


def test_status_helpers():
    assert "text-gain" in x.status_class("success")
    assert "text-loss" in x.status_class("failure")
    assert "text-warn" in x.status_class("warn")
    assert x.status_class("unknown") == x.FLAT
    assert x.status_text("fail") == "Problem"
    assert x.status_text("other") == "other"


def test_short_agent():
    assert x.short_agent("Mozilla/5.0 Gecko/20100101 Firefox/130.0") == "Firefox"
    assert x.short_agent("Mozilla/5.0 Chrome/120 Safari/537 Edg/120") == "Edge"
    assert x.short_agent("") == "–"
    assert x.short_agent("x" * 100) == "x" * 30


def test_bar_chart_draws_a_bar_for_each_value():
    svg = str(x.bar_chart("Runs", ["1 Oct", "2 Oct", "3 Oct"], [4, 0, 2], [0, 1, 0]))

    assert svg.count("<rect") == 3  # Two value bars and one alert bar. Zero draws nothing.
    assert "fill-accent" in svg
    assert "fill-loss" in svg
    assert 'role="img"' in svg
    assert "<table" in svg  # A table for screen readers.


def test_bar_chart_without_data_does_not_fail():
    svg = str(x.bar_chart("Empty", [], [], None))

    assert "<svg" in svg
    assert "<rect" not in svg


def test_bar_chart_escapes_labels():
    svg = str(x.bar_chart('"><script>', ["<b>one</b>"], [1], None))

    assert "<script>" not in svg
    assert "<b>one</b>" not in svg
