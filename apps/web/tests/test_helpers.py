"""Tests for the Datastar helpers and the template filters."""

import json

import pytest
from django.test import RequestFactory

from apps.web.datastar import is_datastar, querystring, read_filters, read_page, signals_json
from apps.web.templatetags import web_extras as f

rf = RequestFactory()
NAMES = ("q", "sentiment", "page")


def test_filters_come_from_plain_query_parameters():
    request = rf.get("/news/", {"q": " bank ", "sentiment": "positive"})

    assert read_filters(request, NAMES) == {"q": "bank", "sentiment": "positive", "page": ""}


def test_filters_come_from_the_datastar_signals():
    signals = json.dumps({"q": "rbi", "sentiment": "", "page": 3, "extra": "x"})
    request = rf.get("/news/", {"datastar": signals}, headers={"Datastar-Request": "true"})

    assert read_filters(request, NAMES) == {"q": "rbi", "sentiment": "", "page": "3"}
    assert is_datastar(request)
    assert not is_datastar(rf.get("/news/"))


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", "null", '"text"'])
def test_bad_datastar_signals_give_empty_filters(raw):
    request = rf.get("/news/", {"datastar": raw})

    assert read_filters(request, NAMES) == {"q": "", "sentiment": "", "page": ""}


def test_a_long_value_is_cut():
    request = rf.get("/news/", {"q": "x" * 500})

    assert len(read_filters(request, NAMES)["q"]) == 100


@pytest.mark.parametrize(
    ("value", "expected"), [("", 1), ("2", 2), ("0", 1), ("-4", 1), ("abc", 1), ("7", 7)]
)
def test_read_page(value, expected):
    assert read_page({"page": value}) == expected


def test_querystring_and_signals_json():
    filters = {"q": "bank", "sentiment": "", "page": "4"}

    assert querystring(filters) == "q=bank"
    assert json.loads(signals_json(filters)) == {"q": "bank", "sentiment": "", "page": "4"}
    assert json.loads(signals_json({"q": ""}))["page"] == "1"


def test_signed_uses_a_real_minus_sign_and_hides_a_rounded_zero():
    assert f.signed(1.25) == "+1.2"
    assert f.signed(-0.4) == "−0.4"
    assert f.signed(0.04) == "0.0"
    assert f.signed(-0.04) == "0.0"
    assert f.signed(0.314, 2) == "+0.31"
    assert f.signed(None) == "–"


def test_percent_tone_and_labels():
    assert f.percent(0.62) == "62%"
    assert f.percent(None) == "–"
    assert f.tone(1) == "text-gain"
    assert f.tone(-1) == "text-loss"
    assert f.tone(0) == f.tone(None) == "text-muted"
    assert f.arrow("up") == "▲"
    assert f.direction_word("down") == "Down"
    assert "gain" in f.badge("good")
    assert "loss" in f.badge("weak")
    assert f.badge("anything else") == f.badge("flat")


def test_money_and_times():
    assert f.rupees(1234) == "₹1,234"
    assert f.rupees(99.5) == "₹99.50"
    assert f.rupees(None) == "–"
    assert f.times(52.34) == "52.3x"
    assert f.times("") == "–"
