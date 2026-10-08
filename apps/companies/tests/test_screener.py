"""Tests for the Screener.in reader.

The sample page below is written from the known Screener.in layout. It is NOT a copy of the live
site, and these tests use no network. They show that the parser and the refresh logic work on a
page with that layout. Run `refresh_companies` on one symbol to check the live site.
"""

from datetime import timedelta

import httpx
import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.companies.models import Company
from apps.companies.screener import (
    MAX_COLUMNS,
    ScreenerParseError,
    parse_company_page,
    parse_number,
    refresh_stale,
)

SAMPLE_PAGE = """<html><body>
<h1 class="margin-0">Example Industries Ltd</h1>
<div class="company-links">
  <a href="https://www.bseindia.com/stock-share-price/example/example/500001/">BSE: 500001</a>
  <a href="https://www.nseindia.com/get-quotes/equity?symbol=EXAMPLE">NSE: EXAMPLE</a>
</div>
<ul id="top-ratios">
  <li><span class="name">Market Cap</span>
      <span class="nowrap value">&#8377; <span class="number">15,80,194</span> Cr.</span></li>
  <li><span class="name">Current Price</span>
      <span class="nowrap value">&#8377; <span class="number">1,168</span></span></li>
  <li><span class="name">High / Low</span>
      <span class="nowrap value">&#8377; <span class="number">1,612</span> /
      <span class="number">1,161</span></span></li>
  <li><span class="name">Stock P/E</span>
      <span class="nowrap value"><span class="number">21.2</span></span></li>
  <li><span class="name">ROCE</span>
      <span class="nowrap value"><span class="number">10.3</span> %</span></li>
</ul>
<section id="peers"><p class="sub">
  <a href="/market/IN07/" title="Sector">Energy</a>
  <a href="/market/IN07/IN0701/">Oil, Gas &amp; Consumable Fuels</a>
</p></section>
<section id="quarters"><table class="data-table">
  <thead><tr><th></th><th>Mar 2025</th><th>Jun 2025</th></tr></thead>
  <tbody>
    <tr><td class="text">Sales&nbsp;<span class="blue-icon">+</span></td>
        <td>2,35,000</td><td>2,40,100</td></tr>
    <tr><td class="text">OPM %</td><td>17%</td><td>-</td></tr>
  </tbody>
</table></section>
</body></html>"""


def test_parse_number():
    assert parse_number("₹ 15,80,194 Cr.") == 1580194.0
    assert parse_number("21.2") == 21.2
    assert parse_number("0.51 %") == 0.51
    assert parse_number("-12.5") == -12.5
    assert parse_number("-") is None
    assert parse_number("") is None


def test_parse_company_page():
    data = parse_company_page(SAMPLE_PAGE)

    assert data["name"] == "Example Industries Ltd"
    assert data["nse_symbol"] == "EXAMPLE"
    assert data["bse_code"] == "500001"
    assert data["sector"] == "Energy"
    assert data["classification"] == ["Energy", "Oil, Gas & Consumable Fuels"]
    assert data["ratios"] == {
        "Market Cap": 1580194.0,
        "Current Price": 1168.0,
        "High": 1612.0,
        "Low": 1161.0,
        "Stock P/E": 21.2,
        "ROCE": 10.3,
    }
    assert data["ratios_text"]["Market Cap"] == "₹ 15,80,194 Cr."
    assert data["tables"]["quarters"] == {
        "periods": ["Mar 2025", "Jun 2025"],
        "rows": {"Sales": [235000.0, 240100.0], "OPM %": [17.0, None]},
    }


def test_parse_keeps_only_the_latest_periods():
    periods = [f"P{n}" for n in range(12)]
    header = "".join(f"<th>{p}</th>" for p in periods)
    cells = "".join(f"<td>{n}</td>" for n in range(12))
    page = SAMPLE_PAGE.replace(
        "</body>",
        f'<section id="profit-loss"><table><thead><tr><th></th>{header}</tr></thead>'
        f"<tbody><tr><td>Sales</td>{cells}</tr></tbody></table></section></body>",
    )

    table = parse_company_page(page)["tables"]["profit_loss"]

    assert len(table["periods"]) == MAX_COLUMNS
    assert table["periods"][-1] == "P11"
    assert table["rows"]["Sales"] == [float(n) for n in range(12 - MAX_COLUMNS, 12)]


def test_a_changed_layout_raises_an_error():
    with pytest.raises(ScreenerParseError):
        parse_company_page("<html><body><h1>Access denied</h1></body></html>")


class Site:
    """A fake Screener.in. It records the paths that were requested."""

    def __init__(self, pages=None, robots=(404, "")):
        self.pages = pages if pages is not None else {}
        self.robots = robots
        self.requested: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requested.append(path)
        if path == "/robots.txt":
            return httpx.Response(self.robots[0], text=self.robots[1])
        status, body = self.pages.get(path, (404, ""))
        return httpx.Response(status, text=body)


def run(site: Site, **kwargs) -> tuple[dict, list[float]]:
    sleeps: list[float] = []
    with httpx.Client(transport=httpx.MockTransport(site)) as client:
        stats = refresh_stale(client=client, sleep=sleeps.append, **kwargs)
    return stats, sleeps


@pytest.fixture
def enabled(settings):
    settings.SCREENER_ENABLED = True


def make_company(symbol="EXAMPLE", **kwargs) -> Company:
    return Company.objects.create(symbol=symbol, name=f"{symbol} Ltd", **kwargs)


@pytest.mark.django_db
def test_nothing_happens_when_screener_is_off():
    make_company()
    site = Site()

    stats, _ = run(site)

    assert stats["disabled"] is True
    assert site.requested == []  # No request, not even robots.txt.


@pytest.mark.django_db
def test_refresh_saves_the_data(enabled):
    company = make_company()
    site = Site(pages={"/company/EXAMPLE/consolidated/": (200, SAMPLE_PAGE)})

    stats, sleeps = run(site)

    company.refresh_from_db()
    assert stats["refreshed"] == 1
    assert company.screener_url == "https://www.screener.in/company/EXAMPLE/consolidated/"
    assert company.screener_data["ratios"]["Stock P/E"] == 21.2
    assert company.screener_data["source"] == "screener.in"
    assert company.sector == "Energy"
    assert company.last_updated is not None
    assert sleeps
    assert all(4.0 < wait <= 5.0 for wait in sleeps)  # SCREENER_DELAY_SECONDS is 5.


@pytest.mark.django_db
def test_standalone_page_is_used_when_there_is_no_consolidated_page(enabled):
    company = make_company()
    site = Site(pages={"/company/EXAMPLE/": (200, SAMPLE_PAGE)})

    stats, _ = run(site)

    company.refresh_from_db()
    assert stats["refreshed"] == 1
    assert company.screener_url == "https://www.screener.in/company/EXAMPLE/"


@pytest.mark.django_db
def test_company_without_a_page_is_marked_and_not_tried_again_soon(enabled):
    company = make_company()

    stats, _ = run(Site())

    company.refresh_from_db()
    assert stats["not_found"] == 1
    assert company.screener_data == {"status": "not_found"}
    assert company.last_updated is not None
    assert run(Site())[0]["not_found"] == 0  # Not stale yet.


@pytest.mark.django_db
def test_robots_txt_disallow_is_obeyed(enabled):
    company = make_company()
    site = Site(
        robots=(200, "User-agent: *\nDisallow: /company/\n"),
        pages={"/company/EXAMPLE/consolidated/": (200, SAMPLE_PAGE)},
    )

    stats, _ = run(site)

    company.refresh_from_db()
    assert stats["blocked"] == 1
    assert "/company/EXAMPLE/consolidated/" not in site.requested
    assert company.screener_data == {"status": "blocked_by_robots"}


@pytest.mark.django_db
def test_server_error_is_tried_again_next_time(enabled):
    company = make_company()

    stats, _ = run(Site(pages={"/company/EXAMPLE/consolidated/": (503, "")}))

    company.refresh_from_db()
    assert stats["failed"] == 1
    assert company.last_updated is None  # Still waiting for a good refresh.


@pytest.mark.django_db
def test_changed_layout_does_not_change_the_company(enabled):
    company = make_company(screener_data={"ratios": {"Stock P/E": 10.0}})
    page = "<html><body><h1>New layout</h1></body></html>"

    stats, _ = run(Site(pages={"/company/EXAMPLE/consolidated/": (200, page)}))

    company.refresh_from_db()
    assert stats["failed"] == 1
    assert company.screener_data == {"ratios": {"Stock P/E": 10.0}}


@pytest.mark.django_db
def test_run_stops_after_many_errors_in_a_row(enabled):
    for n in range(8):
        make_company(f"SYM{n}")
    site = Site(pages={f"/company/SYM{n}/consolidated/": (503, "") for n in range(8)})

    stats, _ = run(site)

    assert stats["failed"] == 5
    assert stats["stopped_early"] is True
    assert sum(path.endswith("/consolidated/") for path in site.requested) == 5


@pytest.mark.django_db
def test_only_old_data_is_refreshed_and_never_fetched_comes_first(enabled):
    make_company("NEWDATA", last_updated=timezone.now() - timedelta(days=1))
    make_company("OLDDATA", last_updated=timezone.now() - timedelta(days=8))
    make_company("NEVER")
    pages = {
        f"/company/{symbol}/consolidated/": (200, SAMPLE_PAGE)
        for symbol in ("NEWDATA", "OLDDATA", "NEVER")
    }
    site = Site(pages=pages)

    stats, _ = run(site)

    page_requests = [path for path in site.requested if path != "/robots.txt"]
    assert stats["refreshed"] == 2
    assert page_requests == ["/company/NEVER/consolidated/", "/company/OLDDATA/consolidated/"]


@pytest.mark.django_db
def test_symbols_and_limit(enabled):
    make_company("AAA", last_updated=timezone.now())
    make_company("BBB")
    make_company("CCC")
    pages = {f"/company/{s}/consolidated/": (200, SAMPLE_PAGE) for s in ("AAA", "BBB", "CCC")}

    assert run(Site(pages=pages), symbols=["AAA"])[0]["refreshed"] == 1  # Even though it is new.
    assert run(Site(pages=pages), limit=1)[0]["refreshed"] == 1  # Only one of BBB and CCC.


@pytest.mark.django_db
def test_refresh_command_says_when_it_is_off(capsys):
    make_company()

    call_command("refresh_companies")

    assert "off" in capsys.readouterr().out
