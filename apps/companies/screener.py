"""Read company data from Screener.in and save it in the Company model.

Legal note: this code is OFF until SCREENER_ENABLED=true. The Screener.in Terms of Service
(https://www.screener.in/guides/terms) allow only "personal, non-commercial transitory viewing".
They forbid copying, mirroring and public display. Saving their data here is close to that, so
turn this on only after you decide that your use is fine. Do not share the data with other people.

To stay a light user, we obey robots.txt, wait several seconds between requests, read each page
at most once a week, and save only the top ratios and the last few periods of the main tables.

The page layout is read from known Screener.in element names. We did not test this against the
live site. If the layout changes, ScreenerParseError is raised and the company is not changed.
"""

import logging
import re
import time
from datetime import timedelta
from urllib.parse import quote

import httpx
from django.db.models import F, Q
from django.utils import timezone
from lxml import html as lxml_html

from apps.news.client import make_client
from apps.news.scraper import PoliteFetcher, RobotsDisallowedError
from apps.siteconfig import conf

from .models import Company

logger = logging.getLogger(__name__)

# Table name in our data -> the id of the section on the Screener.in page.
TABLE_SECTIONS = {
    "quarters": "quarters",
    "profit_loss": "profit-loss",
    "balance_sheet": "balance-sheet",
    "cash_flow": "cash-flow",
    "ratios": "ratios",
    "shareholding": "shareholding",
}
MAX_COLUMNS = 8  # We keep the latest 8 periods of each table.
MAX_CONSECUTIVE_ERRORS = 5  # Stop the run if the page layout seems to have changed.
HTTP_NOT_FOUND = 404


class ScreenerError(Exception):
    """Base class for Screener.in errors."""


class ScreenerNotFoundError(ScreenerError):
    """Screener.in has no page for this symbol."""


class ScreenerParseError(ScreenerError):
    """The page does not have the layout that we expect."""


def parse_number(text: str) -> float | None:
    """Read a number from text like "₹ 15,80,194 Cr." or "21.2" or "0.51 %". Return None if none."""
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group()) if match else None


def _text(node) -> str:
    """Return the text of an HTML node, with single spaces."""
    return " ".join(node.text_content().replace("\xa0", " ").split())


def _parse_top_ratios(root) -> tuple[dict, dict]:
    """Return the top ratios as numbers, and the same ratios as the raw text."""
    ratios: dict[str, float | None] = {}
    ratios_text: dict[str, str] = {}
    for item in root.xpath('//ul[@id="top-ratios"]/li'):
        names = item.xpath('.//span[contains(@class, "name")]')
        values = item.xpath('.//span[contains(@class, "value")]')
        if not names or not values:
            continue
        label, raw = _text(names[0]), _text(values[0])
        ratios_text[label] = raw
        numbers = [parse_number(part) for part in re.findall(r"-?[\d,]+(?:\.\d+)?", raw)]
        labels = [part.strip() for part in label.split("/")]
        if len(labels) > 1 and len(labels) == len(numbers):  # For example "High / Low".
            ratios.update(zip(labels, numbers, strict=True))
        else:
            ratios[label] = numbers[0] if numbers else None
    return ratios, ratios_text


def _parse_table(section) -> dict | None:
    """Return the periods and rows of the first table in a section, or None if it is empty."""
    tables = section.xpath(".//table")
    if not tables:
        return None
    table = tables[0]
    periods = [_text(th) for th in table.xpath(".//thead//th")][1:]
    rows: dict[str, list[float | None]] = {}
    for row in table.xpath(".//tbody/tr"):
        cells = row.xpath("./td")
        label = re.sub(r"\s*\+$", "", _text(cells[0])).strip() if cells else ""
        if len(cells) > 1 and label:
            rows[label] = [parse_number(_text(cell)) for cell in cells[1:]]
    if not periods or not rows:
        return None
    last = slice(-MAX_COLUMNS, None)
    return {
        "periods": periods[last],
        "rows": {label: values[last] for label, values in rows.items()},
    }


def parse_company_page(page: str) -> dict:
    """Read a Screener.in company page. Raise ScreenerParseError if the layout is not known."""
    root = lxml_html.fromstring(page)
    ratios, ratios_text = _parse_top_ratios(root)
    if not ratios:
        raise ScreenerParseError(
            "The top ratios list was not found. The page layout may have changed."
        )

    names = root.xpath("//h1")
    classification: list[str] = []
    for link in root.xpath('//section[@id="peers"]//a[starts-with(@href, "/market/")]'):
        text = _text(link)
        if text and text not in classification:
            classification.append(text)

    nse = bse = ""
    for link in root.xpath('//a[contains(@href, "nseindia.com")]'):
        if match := re.search(r"NSE:\s*([A-Z0-9&_-]+)", _text(link)):
            nse = match.group(1)
    for link in root.xpath('//a[contains(@href, "bseindia.com")]'):
        if match := re.search(r"BSE:\s*(\d+)", _text(link)):
            bse = match.group(1)

    tables = {}
    for key, section_id in TABLE_SECTIONS.items():
        for section in root.xpath(f'//section[@id="{section_id}"]'):
            if table := _parse_table(section):
                tables[key] = table
    return {
        "name": _text(names[0]) if names else "",
        "nse_symbol": nse,
        "bse_code": bse,
        "sector": classification[0] if classification else "",
        "classification": classification,
        "ratios": ratios,
        "ratios_text": ratios_text,
        "tables": tables,
    }


def fetch_company_page(symbol: str, fetcher: PoliteFetcher) -> tuple[str, str]:
    """Download the page of a company. Try the consolidated view first. Return (url, html)."""
    for suffix in ("consolidated/", ""):
        url = f"{conf.SCREENER_BASE_URL.rstrip('/')}/company/{quote(symbol, safe='')}/{suffix}"
        response = fetcher.get(url)  # Can raise RobotsDisallowedError or httpx.HTTPError.
        if response.status_code == HTTP_NOT_FOUND:
            continue
        response.raise_for_status()
        return url, response.text
    raise ScreenerNotFoundError(symbol)


def refresh_company(company: Company, fetcher: PoliteFetcher) -> None:
    """Download and save the Screener.in data for one company."""
    url, page = fetch_company_page(company.symbol, fetcher)
    data = parse_company_page(page)
    company.screener_url = url
    company.screener_data = {
        "source": "screener.in",
        "nse_symbol": data["nse_symbol"],
        "bse_code": data["bse_code"],
        "classification": data["classification"],
        "ratios": data["ratios"],
        "ratios_text": data["ratios_text"],
        "tables": data["tables"],
    }
    if data["sector"]:
        company.sector = data["sector"]
    company.last_updated = timezone.now()
    company.save(update_fields=["screener_url", "screener_data", "sector", "last_updated"])


def _mark_checked(company: Company, status: str) -> None:
    """Remember that we looked, so we do not try again until the next refresh time."""
    company.screener_data = {"status": status}
    company.last_updated = timezone.now()
    company.save(update_fields=["screener_data", "last_updated"])


def stale_companies(max_age_days: int | None = None):
    """Companies with no data, or data older than max_age_days. Never fetched first."""
    days = conf.SCREENER_REFRESH_DAYS if max_age_days is None else max_age_days
    cutoff = timezone.now() - timedelta(days=days)
    return Company.objects.filter(
        Q(last_updated__isnull=True) | Q(last_updated__lt=cutoff)
    ).order_by(F("last_updated").asc(nulls_first=True), "id")


def refresh_stale(
    limit: int | None = None,
    symbols: list[str] | None = None,
    force: bool = False,
    client: httpx.Client | None = None,
    sleep=time.sleep,
    clock=time.monotonic,
) -> dict:
    """Refresh the companies that need it. Return the number of companies for each result.

    symbols: refresh these companies now, even if their data is new.
    force: refresh all companies (oldest data first), even if their data is new.
    """
    stats = {"refreshed": 0, "not_found": 0, "blocked": 0, "failed": 0, "stopped_early": False}
    if not conf.SCREENER_ENABLED:
        return {**stats, "disabled": True}

    if symbols:
        companies = Company.objects.filter(symbol__in=symbols).order_by("symbol")
    elif force:
        companies = Company.objects.order_by(F("last_updated").asc(nulls_first=True), "id")
    else:
        companies = stale_companies()
    companies = companies[: limit or conf.SCREENER_BATCH_SIZE]

    own_client = client is None
    client = client or make_client()
    fetcher = PoliteFetcher(
        client,
        delay=conf.SCREENER_DELAY_SECONDS,
        user_agent=conf.NEWS_USER_AGENT,
        sleep=sleep,
        clock=clock,
    )
    errors_in_a_row = 0
    try:
        for company in companies:
            try:
                refresh_company(company, fetcher)
            except ScreenerNotFoundError:
                logger.warning("Screener.in has no page for %s", company.symbol)
                _mark_checked(company, "not_found")
                stats["not_found"] += 1
            except RobotsDisallowedError:
                logger.warning("robots.txt does not allow the page for %s", company.symbol)
                _mark_checked(company, "blocked_by_robots")
                stats["blocked"] += 1
            except (httpx.HTTPError, ScreenerParseError) as exc:
                logger.warning("Screener.in refresh failed for %s: %s", company.symbol, exc)
                stats["failed"] += 1
                errors_in_a_row += 1
                if errors_in_a_row >= MAX_CONSECUTIVE_ERRORS:
                    logger.exception(
                        "Stop: %d errors in a row. Check the page layout.", errors_in_a_row
                    )
                    stats["stopped_early"] = True
                    break
                continue
            else:
                stats["refreshed"] += 1
            errors_in_a_row = 0
    finally:
        if own_client:
            client.close()
    return stats
