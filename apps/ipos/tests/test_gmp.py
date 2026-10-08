"""Tests for the GMP table reader. They do not use the network."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from apps.ipos.gmp import (
    GmpRow,
    GmpSourceError,
    apply_gmp_rows,
    clean_gmp_name,
    parse_gmp_table,
    parse_gmp_value,
    parse_subscription_value,
    parse_updated_on,
    update_gmp,
)
from apps.ipos.models import Ipo
from apps.news.scraper import PoliteFetcher

from .helpers import IST, NOW, make_ipo, set_stamps

pytestmark = pytest.mark.django_db

D = Decimal

PAGE = """
<html><body>
<table><tr><th>Other</th></tr><tr><td>1</td></tr></table>
<table>
<thead><tr>
  <th>Name</th><th>GMP</th><th>Rating</th><th>Sub</th><th>Price (₹)</th><th>IPO Size</th>
  <th>Lot</th><th>Open</th><th>Close</th><th>BoA Dt</th><th>Listing</th>
  <th>Updated-On</th><th>Anchor</th>
</tr></thead>
<tbody>
<tr>
  <td><a href="/ipo/acme">Acme Foods Ltd IPO</a> <span>O</span></td><td>₹12 (12.0%)</td>
  <td>★★★</td><td>52.3x</td><td>100</td><td>₹500 Cr</td><td>150</td><td>5-Oct</td>
  <td>7-Oct</td><td>8-Oct</td><td>12-Oct</td><td>5-Oct 12:37</td><td>Yes</td>
</tr>
<tr>
  <td><a href="/ipo/beta">Beta Tools IPO</a></td><td>₹-4</td><td>★</td><td>0.4x</td>
  <td>100</td><td>₹90 Cr</td><td>100</td><td>5-Oct</td><td>7-Oct</td><td>8-Oct</td>
  <td>12-Oct</td><td>5-Oct 09:05</td><td>No</td>
</tr>
<tr>
  <td><a href="/ipo/old">Old Time Ltd IPO</a></td><td>--</td><td>-</td><td>-</td>
  <td>50</td><td>₹10 Cr</td><td>100</td><td>1-Sep</td><td>3-Sep</td><td>4-Sep</td>
  <td>8-Sep</td><td>-</td><td>No</td>
</tr>
<tr><td colspan="13">A note row</td></tr>
</tbody></table>
</body></html>
"""

LATER = NOW + timedelta(hours=2)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("₹12", D("12")),
        ("₹ -5", D("-5")),
        ("₹12 (12.0%)", D("12")),
        ("Rs. 7 (3%)", D("7")),
        ("−3", D("-3")),  # A real minus sign.
        ("12", D("12")),
        ("--", None),
        ("-", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_gmp_value(text, expected):
    assert parse_gmp_value(text) == expected


def test_parse_subscription_value():
    assert parse_subscription_value("52.3x") == D("52.3")
    assert parse_subscription_value("0.4 X") == D("0.4")
    assert parse_subscription_value("1,204.5") == D("1204.5")
    assert parse_subscription_value("-") is None


def test_parse_updated_on_reads_the_time_in_india_time():
    assert parse_updated_on("5-Oct 12:37", NOW) == datetime(2026, 10, 5, 12, 37, tzinfo=IST)
    assert parse_updated_on("05-Oct-2026 09:05", NOW) == datetime(2026, 10, 5, 9, 5, tzinfo=IST)
    assert parse_updated_on("5 October 2026, 1:30 PM", NOW) == datetime(
        2026, 10, 5, 13, 30, tzinfo=IST
    )
    assert parse_updated_on("5-Oct 12:05 am", NOW) == datetime(2026, 10, 5, 0, 5, tzinfo=IST)


def test_a_time_without_a_year_in_the_future_is_from_last_year():
    january = datetime(2027, 1, 2, 9, 0, tzinfo=IST)

    assert parse_updated_on("30-Dec 18:00", january) == datetime(2026, 12, 30, 18, 0, tzinfo=IST)


@pytest.mark.parametrize(
    "text", ["", "-", "Oct", "5-Foo 12:00", "31-Feb 10:00", "5-Oct 25:00", None]
)
def test_parse_updated_on_gives_none_for_a_bad_time(text):
    assert parse_updated_on(text, NOW) is None


def test_clean_gmp_name():
    assert clean_gmp_name("Acme Foods Ltd IPO") == "Acme Foods Ltd"
    assert clean_gmp_name("  Acme   Foods Ltd IPO (O) ") == "Acme Foods Ltd"
    assert clean_gmp_name("Acme Foods") == "Acme Foods"


def test_parse_gmp_table_reads_the_rows_by_column_name():
    rows = parse_gmp_table(PAGE, NOW)

    assert [r.name for r in rows] == ["Acme Foods Ltd", "Beta Tools", "Old Time Ltd"]
    acme, beta, old = rows
    assert (acme.gmp, acme.subscription_times) == (D("12"), D("52.3"))
    assert acme.updated_at == datetime(2026, 10, 5, 12, 37, tzinfo=IST)
    assert (beta.gmp, beta.subscription_times) == (D("-4"), D("0.4"))
    assert (old.gmp, old.subscription_times, old.updated_at) == (None, None, None)


def test_the_columns_can_be_in_another_order():
    page = (
        "<table><tr><th>Updated-On</th><th>Sub</th><th>GMP</th><th>Name</th></tr>"
        "<tr><td>5-Oct 10:00</td><td>2.5x</td><td>₹8</td><td><a>Gamma Ltd IPO</a></td></tr></table>"
    )

    (row,) = parse_gmp_table(page, NOW)

    assert (row.name, row.gmp, row.subscription_times) == ("Gamma Ltd", D("8"), D("2.5"))


def test_a_page_without_the_table_names_the_columns_that_it_found():
    page = "<table><tr><th>Name</th><th>Price</th></tr><tr><td>x</td><td>1</td></tr></table>"

    with pytest.raises(GmpSourceError, match="Name, Price"):
        parse_gmp_table(page, NOW)


@pytest.mark.parametrize("page", ["", "<html><body><p>No table</p></body></html>"])
def test_a_page_without_any_table_is_an_error(page):
    with pytest.raises(GmpSourceError):
        parse_gmp_table(page, NOW)


def test_apply_gmp_rows_sets_the_values_and_the_source_time():
    ipo = make_ipo("Acme Foods Limited", price_band_high=D("100"))
    rows = parse_gmp_table(PAGE, NOW)

    result = apply_gmp_rows(rows, NOW)

    ipo.refresh_from_db()
    assert (ipo.gmp, ipo.subscription_times) == (D("12"), D("52.3"))
    assert ipo.gmp_updated_at == datetime(2026, 10, 5, 12, 37, tzinfo=IST)
    assert ipo.subscription_updated_at == ipo.gmp_updated_at
    assert (result.rows, result.matched, result.updated) == (3, 1, 1)
    assert result.unmatched == ["Beta Tools", "Old Time Ltd"]


def test_a_manual_value_that_is_newer_is_not_replaced():
    ipo = make_ipo("Acme Foods Limited", gmp=D("30"), subscription_times=D("60"))
    set_stamps(ipo, gmp_at=LATER, subscription_at=LATER)
    rows = [GmpRow("Acme Foods Ltd", D("12"), D("52.3"), NOW)]

    result = apply_gmp_rows(rows, NOW)

    ipo.refresh_from_db()
    assert (ipo.gmp, ipo.subscription_times) == (D("30"), D("60"))
    assert (result.updated, result.older, result.unchanged) == (0, 1, 1)


def test_a_newer_value_from_the_source_replaces_an_old_one():
    ipo = make_ipo("Acme Foods Limited", gmp=D("30"))
    set_stamps(ipo, gmp_at=NOW - timedelta(days=1), subscription_at=None)
    rows = [GmpRow("Acme Foods Ltd", D("12"), None, NOW)]

    apply_gmp_rows(rows, NOW)

    ipo.refresh_from_db()
    assert ipo.gmp == D("12")
    assert ipo.gmp_updated_at == NOW


def test_a_row_without_a_time_gets_the_time_of_the_fetch():
    ipo = make_ipo("Acme Foods Limited")
    rows = [GmpRow("Acme Foods Ltd", D("12"), None, None)]

    apply_gmp_rows(rows, NOW)

    ipo.refresh_from_db()
    assert ipo.gmp_updated_at == NOW


def test_a_gmp_that_is_far_too_big_is_skipped():
    ipo = make_ipo("Acme Foods Limited", price_band_high=D("100"))
    rows = [GmpRow("Acme Foods Ltd", D("900"), None, NOW)]

    result = apply_gmp_rows(rows, NOW)

    ipo.refresh_from_db()
    assert ipo.gmp is None
    assert result.suspect == 1


def test_a_listed_ipo_is_not_changed():
    ipo = make_ipo("Acme Foods Limited", listing_gain_pct=5.0, status=Ipo.Status.LISTED)
    rows = [GmpRow("Acme Foods Ltd", D("12"), D("5"), NOW)]

    result = apply_gmp_rows(rows, NOW)

    ipo.refresh_from_db()
    assert ipo.gmp is None
    assert result.matched == 0


def test_a_source_name_that_starts_like_a_saved_name_matches_if_only_one_does():
    one = make_ipo("Acme Foods India Limited")
    rows = [GmpRow("Acme Foods", D("12"), None, NOW)]

    assert apply_gmp_rows(rows, NOW).matched == 1
    one.refresh_from_db()
    assert one.gmp == D("12")


def test_two_possible_ipos_give_no_match():
    make_ipo("Acme Foods India Limited")
    make_ipo("Acme Foods Exports Limited")
    rows = [GmpRow("Acme Foods", D("12"), None, NOW)]

    result = apply_gmp_rows(rows, NOW)

    assert result.matched == 0
    assert result.unmatched == ["Acme Foods"]


def test_a_short_name_is_not_matched_by_its_start():
    make_ipo("Zen Technologies Limited")
    rows = [GmpRow("Zen", D("12"), None, NOW)]

    assert apply_gmp_rows(rows, NOW).matched == 0


def make_fetcher(handler) -> PoliteFetcher:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return PoliteFetcher(client, delay=0, user_agent="KashEngineBot/0.1", sleep=lambda _: None)


def robots_ok(request, page=PAGE, status=200):
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")
    return httpx.Response(status, text=page)


def test_update_gmp_downloads_the_page_and_saves(tmp_path):
    ipo = make_ipo("Acme Foods Limited")
    saved = tmp_path / "page.html"

    result = update_gmp(make_fetcher(robots_ok), "https://gmp.test/live", NOW, saved)

    ipo.refresh_from_db()
    assert ipo.gmp == D("12")
    assert result.updated == 1
    assert "Acme Foods Ltd IPO" in saved.read_text(encoding="utf-8")


def test_update_gmp_reports_http_errors():
    fetcher = make_fetcher(lambda r: robots_ok(r, "oops", 503))

    with pytest.raises(GmpSourceError, match="HTTP 503"):
        update_gmp(fetcher, "https://gmp.test/live", NOW)


def test_update_gmp_obeys_robots_txt():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        pytest.fail("must not fetch the page")

    with pytest.raises(GmpSourceError, match=r"robots\.txt"):
        update_gmp(make_fetcher(handler), "https://gmp.test/live", NOW)


def test_update_gmp_reports_network_errors():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        raise httpx.ConnectError("no route")

    with pytest.raises(GmpSourceError, match="no route"):
        update_gmp(make_fetcher(handler), "https://gmp.test/live", NOW)


def test_update_gmp_uses_the_url_from_the_settings(settings):
    settings.IPO_GMP_URL = "https://gmp.test/from-settings"
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return robots_ok(request)

    update_gmp(make_fetcher(handler), now=NOW)

    assert "https://gmp.test/from-settings" in seen


# apps/ipos/tests/data/gmp_page_sample.html is the table of the live page, cut to 6 rows. It was
# saved on 7 Oct 2026 with `refresh_ipo_data --save-page`.

SAMPLE = Path(__file__).parent / "data" / "gmp_page_sample.html"
SAMPLE_NOW = datetime(2026, 10, 7, 12, 0, tzinfo=IST)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("₹167 (-%)148 ↓ / 167 ↑", D("167")),
        ("₹15 (18.29%)7 ↓ / 15 ↑", D("15")),
        ("₹-- (0.00%)0 ↓ / 0 ↑", None),  # No GMP. The 0.00% must not become a GMP of 0.
        ("₹--", None),
        ("₹0 (0.00%)", D("0")),  # A real GMP of zero.
        ("₹-5 (-5.00%)", D("-5")),
        ("₹1,234 (10%)", D("1234")),
    ],
)
def test_parse_gmp_value_on_the_texts_of_the_live_page(text, expected):
    assert parse_gmp_value(text) == expected


def test_the_live_page_sample_is_read_correctly():
    rows = parse_gmp_table(SAMPLE.read_text(encoding="utf-8"), SAMPLE_NOW)

    assert [r.name for r in rows] == [
        "Jio Platforms",
        "HD Fire Protect",
        "R.K.Fashion Accessories",
        "TNA Solutions",
        "Acme India Industries",
        "Paramount Syntex",
    ]
    jio, hd_fire, fashion, tna, acme, paramount = rows
    assert (jio.gmp, jio.subscription_times) == (D("167"), None)
    assert (hd_fire.gmp, hd_fire.subscription_times) == (None, None)  # "₹--" and "-".
    assert (fashion.gmp, fashion.subscription_times) == (D("15"), D("0.44"))
    assert (tna.gmp, tna.subscription_times) == (D("3"), D("55.2"))
    assert (acme.gmp, acme.subscription_times) == (D("65"), D("124.23"))
    assert (paramount.gmp, paramount.subscription_times) == (None, D("1.88"))
    assert fashion.updated_at == datetime(2026, 10, 7, 9, 37, tzinfo=IST)


def test_the_live_page_sample_updates_a_saved_ipo():
    ipo = make_ipo("R.K.Fashion Accessories Limited", price_band_high=D("82"))
    rows = parse_gmp_table(SAMPLE.read_text(encoding="utf-8"), SAMPLE_NOW)

    apply_gmp_rows(rows, SAMPLE_NOW)

    ipo.refresh_from_db()
    assert (ipo.gmp, ipo.subscription_times) == (D("15"), D("0.44"))
    assert ipo.gmp_updated_at == datetime(2026, 10, 7, 9, 37, tzinfo=IST)
