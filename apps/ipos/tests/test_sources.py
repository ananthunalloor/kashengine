"""Tests for the IPO page parser. They do not use the network."""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from apps.ipos.sources import (
    MAINBOARD,
    SME,
    IpoSourceError,
    clean_name,
    fetch_records,
    parse_date,
    parse_ipo_json,
    parse_ipo_table,
    parse_issue_size_cr,
    parse_number,
    parse_percent,
    parse_price_band,
    parse_response,
)
from apps.news.scraper import PoliteFetcher

PAGE = """
<html><body>
<table><tr><th>Other</th><th>Table</th></tr><tr><td>1</td><td>2</td></tr></table>
<table>
<thead><tr>
  <th>Company Name</th><th>Issue Size (₹ Cr.)</th><th>Price Band</th><th>Open Date</th>
  <th>Close Date</th><th>Listing Date</th><th>Exchange</th><th>Lead Manager</th>
  <th>Listing Gain (%)</th>
</tr></thead>
<tbody>
<tr>
  <td><a href="/ipo/acme-foods-ipo/1/">Acme Foods Ltd. IPO</a></td><td>1,250.50</td>
  <td>₹ 100 to ₹ 105</td><td>Oct 6, 2026</td><td>Oct 8, 2026</td><td>Oct 13, 2026</td>
  <td>BSE, NSE</td><td>Some Bank</td><td></td>
</tr>
<tr>
  <td><a href="/ipo/tiny-tech/2/">Tiny Tech Limited</a></td><td>32.4</td><td>71</td>
  <td>Sep 1, 2026</td><td>Sep 3, 2026</td><td>Sep 8, 2026</td><td>NSE SME</td><td>X</td>
  <td>+25.5%</td>
</tr>
<tr>
  <td><s>Withdrawn Co IPO</s></td><td>10</td><td>50</td><td>Aug 1, 2026</td><td>Aug 3, 2026</td>
  <td>-</td><td>BSE</td><td>Y</td><td></td>
</tr>
<tr><td colspan="9">A note row</td></tr>
</tbody></table>
</body></html>
"""


def test_parse_date():
    assert parse_date("Oct 6, 2026") == date(2026, 10, 6)
    assert parse_date("6th October 2026") == date(2026, 10, 6)
    assert parse_date("06-Oct-2026") == date(2026, 10, 6)
    assert parse_date("2026-10-06") == date(2026, 10, 6)
    assert parse_date("06/10/2026") == date(2026, 10, 6)
    for empty in ("", "-", "TBA", None, "soon"):
        assert parse_date(empty) is None


def test_parse_numbers():
    assert parse_number("₹ 1,234.50 Cr") == Decimal("1234.50")
    assert parse_number("none") is None
    assert parse_price_band("₹ 100 to ₹ 105") == (Decimal("100"), Decimal("105"))
    assert parse_price_band("105") == (Decimal("105"), Decimal("105"))
    assert parse_price_band("TBA") == (None, None)
    assert parse_issue_size_cr("₹ 250 Cr") == Decimal("250")
    assert parse_issue_size_cr("50 Lakh") == Decimal("0.5")
    assert parse_issue_size_cr("-") is None
    assert parse_percent("+12.5%") == 12.5
    assert parse_percent("−3.2 %") == -3.2
    assert parse_percent("") is None


def test_clean_name():
    assert clean_name("  Acme   Foods Ltd. IPO ") == "Acme Foods Ltd."
    assert clean_name("Ipoland Ltd") == "Ipoland Ltd"


def test_parse_ipo_table_reads_rows_and_skips_withdrawn_and_note_rows():
    records = parse_ipo_table(PAGE, "https://src.test/list/")

    assert [r.name for r in records] == ["Acme Foods Ltd.", "Tiny Tech Limited"]
    acme, tiny = records
    assert acme.open_date == date(2026, 10, 6)
    assert acme.close_date == date(2026, 10, 8)
    assert acme.listing_date == date(2026, 10, 13)
    assert (acme.price_band_low, acme.price_band_high) == (Decimal("100"), Decimal("105"))
    assert acme.issue_size_cr == Decimal("1250.50")
    assert acme.category == MAINBOARD
    assert acme.listing_gain_pct is None
    assert acme.source_url == "https://src.test/ipo/acme-foods-ipo/1/"
    assert tiny.category == SME
    assert tiny.listing_gain_pct == 25.5
    assert tiny.price_band_high == Decimal("71")


def test_columns_are_found_by_name_not_by_position():
    page = """
    <table><tr><th>Close Date</th><th>Open Date</th><th>Issuer</th><th>Issue Price</th></tr>
    <tr><td>Oct 8, 2026</td><td>Oct 6, 2026</td><td>Zed Ltd</td><td>₹ 90</td></tr></table>
    """
    [record] = parse_ipo_table(page)

    assert record.name == "Zed Ltd"
    assert record.open_date == date(2026, 10, 6)
    assert record.close_date == date(2026, 10, 8)
    assert record.price_band_high == Decimal("90")


def test_the_listing_day_close_column_is_not_the_close_date():
    page = """
    <table><tr><th>Company</th><th>Open</th><th>Close</th><th>Listing Day Close</th></tr>
    <tr><td>Zed Ltd</td><td>Oct 6, 2026</td><td>Oct 8, 2026</td><td>₹ 140</td></tr></table>
    """
    [record] = parse_ipo_table(page)

    assert record.close_date == date(2026, 10, 8)


@pytest.mark.parametrize("page", ["", "<html></html>", "not html at all <<<", "<table></table>"])
def test_a_page_without_the_table_gives_no_records(page):
    assert parse_ipo_table(page) == []


# --- Fetching ------------------------------------------------------------------------------


def make_fetcher(handler) -> PoliteFetcher:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return PoliteFetcher(
        client, delay=0, user_agent="Mozilla/5.0 (compatible; TestBot/1.0)", sleep=lambda s: None
    )


def site(page_status=200, page_text=PAGE, robots="User-agent: *\nAllow: /"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        return httpx.Response(page_status, text=page_text)

    return handler


def test_fetch_records_reads_the_page():
    records = fetch_records("https://src.test/list/", make_fetcher(site()))

    assert len(records) == 2


def test_fetch_records_obeys_robots_txt():
    fetcher = make_fetcher(site(robots="User-agent: *\nDisallow: /list/"))

    with pytest.raises(IpoSourceError, match="robots.txt"):
        fetch_records("https://src.test/list/", fetcher)


def test_fetch_records_reports_http_errors_and_a_changed_page():
    with pytest.raises(IpoSourceError, match="HTTP 503"):
        fetch_records("https://src.test/list/", make_fetcher(site(page_status=503)))
    with pytest.raises(IpoSourceError, match="no IPOs found"):
        fetch_records("https://src.test/list/", make_fetcher(site(page_text="<p>new design</p>")))


def test_fetch_records_reports_network_errors():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        raise httpx.ConnectError("down")

    with pytest.raises(IpoSourceError, match="down"):
        fetch_records("https://src.test/list/", make_fetcher(handler))


# --- The JSON feed -------------------------------------------------------------------------

FEED = {
    "msg": 0,
    "sSearchWhere": "",
    "reportTableData": [
        {
            "Company": '<a href="https://www.chittorgarh.com/ipo/jio-platforms-ipo/3152/" '
            'title="Jio Platforms IPO Details">Jio Platforms Ltd.</a>',
            "Issue Category": "Mainboard",
            "Opening Date": "",
            "Closing Date": "",
            "Listing Date": "",
            "Issue Price (Rs.)": "",
            "Total Issue Amount (Incl.Firm reservations) (Rs.cr.)": "0.00",
            "Issue Amount (Rs.cr.)": "0.00",
            "~Issue_Open_Date": "2027-01-13T11:50:00.000Z",
            "Listing at": "BSE, NSE",
        },
        {
            "Company": '<a href="https://www.chittorgarh.com/ipo/rkfashion-accessories-ipo/3138/">'
            "R.K.Fashion Accessories Ltd.</a>",
            "Issue Category": "SME",
            "Opening Date": "05-Oct-2026",
            "Closing Date": "07-Oct-2026",
            "Listing Date": "",
            "Issue Price (Rs.)": "77.00 to 82.00",
            "Total Issue Amount (Incl.Firm reservations) (Rs.cr.)": "34.99",
            "Issue Amount (Rs.cr.)": "33.23",
            "~Issue_Open_Date": "2026-10-05T00:00:00.000Z",
            "~ListingDate": "2026-10-12T00:00:00.000Z",
            "Listing at": "NSE SME",
        },
        {
            "Company": "Vishal Nirmiti Ltd.",
            "Issue Category": "Mainboard",
            "Opening Date": "30-Sep-2026",
            "Closing Date": "05-Oct-2026",
            "Listing Date": "08-Oct-2026",
            "Issue Price (Rs.)": "220.00",
            "Issue Amount (Rs.cr.)": "410.5",
            "~nse_symbol": "vishal ",
            "~bse_script_code": "544999",
            "~isin": "ine0abc01012",
        },
        {"Company": "", "Opening Date": "05-Oct-2026"},
    ],
}


def test_parse_ipo_json_reads_the_rows_of_the_feed():
    records = parse_ipo_json(FEED, "https://feed.test/data")

    assert [r.name for r in records] == [
        "Jio Platforms Ltd.",
        "R.K.Fashion Accessories Ltd.",
        "Vishal Nirmiti Ltd.",
    ]
    jio, fashion, vishal = records
    assert jio.open_date is None  # The planned date (a field with ~) is not used.
    assert jio.issue_size_cr is None  # 0.00 means "not known".
    assert jio.price_band_high is None
    assert jio.category == MAINBOARD
    assert jio.source_url == "https://www.chittorgarh.com/ipo/jio-platforms-ipo/3152/"
    assert fashion.category == SME
    assert fashion.open_date == date(2026, 10, 5)
    assert fashion.close_date == date(2026, 10, 7)
    assert fashion.listing_date is None
    assert (fashion.price_band_low, fashion.price_band_high) == (Decimal("77"), Decimal("82"))
    assert fashion.issue_size_cr == Decimal("34.99")  # The total, not the net amount.
    assert vishal.price_band_high == Decimal("220")
    assert vishal.issue_size_cr == Decimal("410.5")  # The fallback field.
    assert vishal.source_url == "https://feed.test/data"  # No link in the row.
    assert (vishal.nse_symbol, vishal.bse_code, vishal.isin) == ("VISHAL", "544999", "INE0ABC01012")
    assert (fashion.nse_symbol, fashion.bse_code, fashion.isin) == ("", "", "")


def test_parse_ipo_json_finds_the_rows_in_other_shapes_and_ignores_bad_data():
    nested = {"data": {"reportTableData": FEED["reportTableData"]}}
    plain_list = FEED["reportTableData"]

    assert len(parse_ipo_json(nested)) == 3
    assert len(parse_ipo_json(plain_list)) == 3
    for bad in ({}, [], "text", None, {"reportTableData": "none"}, {"reportTableData": [1, 2]}):
        assert parse_ipo_json(bad) == []


def test_parse_response_picks_json_or_html():
    import json

    assert len(parse_response(json.dumps(FEED), "u", "application/json")) == 3
    assert len(parse_response(json.dumps(FEED), "u", "text/plain")) == 3  # It looks like JSON.
    assert len(parse_response(PAGE, "u", "text/html")) == 2
    with pytest.raises(IpoSourceError, match="not valid JSON"):
        parse_response("{broken", "u", "application/json")


def test_fetch_records_reads_a_json_feed():
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(
            200, text=json.dumps(FEED), headers={"content-type": "application/json"}
        )

    records = fetch_records("https://feed.test/data", make_fetcher(handler))

    assert len(records) == 3


def test_fetch_records_reports_an_empty_feed():
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text=json.dumps({"reportTableData": []}))

    with pytest.raises(IpoSourceError, match="no IPOs found"):
        fetch_records("https://feed.test/data", make_fetcher(handler))
