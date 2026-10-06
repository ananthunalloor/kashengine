"""Read the IPO list from a web page.

READ THIS FIRST.
- The default source is the IPO list of
  chittorgarh.com. Its robots.txt allows the page. We could not find a written permission or a
  written ban for automated use, and the footer says "All rights reserved". Read their terms
  before you turn the fetch on. Use the data for yourself only. Do not publish it.
- We read one page, one or two times a day, and we obey robots.txt (PoliteFetcher).
- Since late 2026 the chittorgarh page has no HTML table. The browser loads the rows from a
  JSON API (webnodejs.chittorgarh.com). For a chittorgarh report URL we read that API instead.
- We could NOT test the parser on the live page when we wrote it (the build server cannot reach
  the site). The parser does not use fixed column numbers or CSS classes. It reads the table
  header names, so a small change of the page should not break it. If the site changes a lot,
  the run saves nothing, logs a warning, and you can still enter IPOs with `import_ipo_csv`,
  `update_ipo`, or the admin.
- This source gives dates, price band, issue size, and the listing gain. It does NOT give the
  GMP (grey market premium) or the subscription. Enter those with `update_ipo` or `import_ipo_csv`.
  GMP is not official data. Treat it with care.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

import httpx
from lxml import html as lxml_html

from apps.news.scraper import PoliteFetcher, RobotsDisallowed

logger = logging.getLogger(__name__)

MAINBOARD = "mainboard"
SME = "sme"


class IpoSourceError(Exception):
    """We could not read the IPO list from a source."""


@dataclass
class IpoRecord:
    """One IPO, as a source or a CSV file gives it. A value of None means "not known"."""

    name: str
    open_date: date | None = None
    close_date: date | None = None
    listing_date: date | None = None
    price_band_low: Decimal | None = None
    price_band_high: Decimal | None = None
    lot_size: int | None = None
    issue_size_cr: Decimal | None = None
    category: str | None = None
    gmp: Decimal | None = None
    subscription_times: Decimal | None = None
    listing_price: Decimal | None = None
    listing_gain_pct: float | None = None
    source_url: str = ""


# --- Small parsers -------------------------------------------------------------------------

DATE_FORMATS = (
    "%b %d, %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %b, %Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
)
_ORDINAL = re.compile(r"(?<=\d)(st|nd|rd|th)\b", re.IGNORECASE)
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def parse_date(text: str | None) -> date | None:
    """Read a date in one of the usual formats. Return None for "-", "TBA", or an empty text."""
    cleaned = _ORDINAL.sub("", (text or "").strip())
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def parse_numbers(text: str | None) -> list[Decimal]:
    """All the numbers in a text. Commas are removed: "1,234.5" gives 1234.5."""
    numbers = []
    for found in _NUMBER.findall(text or ""):
        try:
            numbers.append(Decimal(found.replace(",", "")))
        except InvalidOperation:
            continue
    return numbers


def parse_number(text: str | None) -> Decimal | None:
    numbers = parse_numbers(text)
    return numbers[0] if numbers else None


def parse_price_band(text: str | None) -> tuple[Decimal | None, Decimal | None]:
    """Read "₹ 100 to ₹ 105", "100 - 105", or "105". Return (low, high)."""
    numbers = [n for n in parse_numbers(text) if n > 0]
    if not numbers:
        return None, None
    return min(numbers), max(numbers)


def parse_issue_size_cr(text: str | None) -> Decimal | None:
    """Read an issue size in crore rupees. A size that says "lakh" is changed to crore."""
    number = parse_number(text)
    if number is None or number <= 0:
        return None
    if re.search(r"lakh|lac", text or "", re.IGNORECASE):
        number = number / 100
    return number


def parse_percent(text: str | None) -> float | None:
    """Read "+12.5%" or "-3.2 %". Return None if there is no number."""
    number = parse_number((text or "").replace("−", "-"))  # A real minus sign (U+2212).
    return None if number is None else float(number)


def clean_name(name: str) -> str:
    """Remove the " IPO" tail and extra spaces from a name."""
    name = " ".join(name.split())
    name = re.sub(r"\s+IPO$", "", name, flags=re.IGNORECASE)
    return name.strip()


# --- The table -----------------------------------------------------------------------------


def _header_field(header: str) -> str | None:
    """Say which field a column header means. The order of the checks matters."""
    h = " ".join(header.lower().split())
    if "listing" in h and "gain" in h:
        return "listing_gain"
    if "listing" in h and "date" in h:
        return "listing_date"
    if "listing" in h:
        return None  # For example "Listing Day Close". We do not use it.
    if re.search(r"company|issuer|ipo name|^name", h):
        return "name"
    if re.search(r"exchange|platform|category", h):
        return "exchange"
    if re.search(r"issue size|issue amount|^amount|^size", h):
        return "issue_size"
    if re.search(r"price band|issue price|^price", h):
        return "price"
    if "open" in h:
        return "open"
    if "clos" in h:
        return "close"
    if "lot" in h:
        return "lot"
    return None


def _column_map(headers: list[str]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for index, header in enumerate(headers):
        field = _header_field(header)
        if field and field not in columns:
            columns[field] = index
    return columns


def _is_withdrawn(cell) -> bool:
    """A name with a line through it means that the IPO was withdrawn."""
    if cell.xpath(".//strike|.//s|.//del"):
        return True
    return any("line-through" in (style or "") for style in cell.xpath(".//@style|./@style"))


def parse_ipo_table(page: str, source_url: str = "") -> list[IpoRecord]:
    """Find the IPO table in a page and read its rows. Return an empty list if there is none.

    The table is the one whose header has a name column and a date column.
    """
    try:
        root = lxml_html.fromstring(page)
    except (ValueError, lxml_html.etree.ParserError):
        return []

    for table in root.iter("table"):
        header_cells = table.xpath(".//thead//th") or table.xpath(".//tr[1]/th|.//tr[1]/td")
        headers = [" ".join(cell.text_content().split()) for cell in header_cells]
        columns = _column_map(headers)
        if "name" not in columns or not ({"open", "close"} & columns.keys()):
            continue

        rows = [row.xpath("./td") for row in table.xpath(".//tr[td]")]
        return _read_rows(columns, len(headers), rows, source_url)
    return []


def parse_ipo_json(text: str, source_url: str = "") -> list[IpoRecord]:
    """Read the rows of the chittorgarh JSON API. Each row maps a column header to cell HTML."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    rows = data.get("reportTableData") if isinstance(data, dict) else None
    if not rows or not isinstance(rows, list) or not isinstance(rows[0], dict):
        return []

    # Keys that start with "~" are hidden helper fields, not columns.
    headers = [key for key in rows[0] if not key.startswith("~")]
    columns = _column_map(headers)
    if "name" not in columns or not ({"open", "close"} & columns.keys()):
        return []
    cell_rows = [
        [lxml_html.fragment_fromstring(str(row.get(h) or ""), create_parent="td") for h in headers]
        for row in rows
        if isinstance(row, dict)
    ]
    return _read_rows(columns, len(headers), cell_rows, source_url)


def _read_rows(columns: dict[str, int], width: int, rows, source_url: str) -> list[IpoRecord]:
    records = []
    for cells in rows:
        if len(cells) < width:
            continue  # A note row or a banner row.

        def text(field: str, cells=cells) -> str:
            index = columns.get(field)
            return " ".join(cells[index].text_content().split()) if index is not None else ""

        name_cell = cells[columns["name"]]
        # Drop status badges such as <span class="badge">CT</span> from the name.
        for badge in name_cell.xpath(".//span[contains(@class, 'badge')]"):
            badge.drop_tree()
        name = clean_name(name_cell.text_content())
        if not name or _is_withdrawn(name_cell):
            continue
        links = name_cell.xpath(".//a/@href")
        low, high = parse_price_band(text("price"))
        lot = parse_number(text("lot"))
        records.append(
            IpoRecord(
                name=name,
                open_date=parse_date(text("open")),
                close_date=parse_date(text("close")),
                listing_date=parse_date(text("listing_date")),
                price_band_low=low,
                price_band_high=high,
                lot_size=int(lot) if lot and lot > 0 else None,
                issue_size_cr=parse_issue_size_cr(text("issue_size")),
                category=SME if "sme" in text("exchange").lower() else MAINBOARD,
                listing_gain_pct=parse_percent(text("listing_gain")),
                source_url=urljoin(source_url, links[0]) if links else source_url,
            )
        )
    return records


_CHITTORGARH_REPORT = re.compile(r"^https?://(?:www\.)?chittorgarh\.com/report/[^/]+/(\d+)/")
CHITTORGARH_API = (
    "https://webnodejs.chittorgarh.com/cloud/report/data-read/"
    "{report_id}/1/{month}/{year}/{fy}/0/all/0?search="
)


def _financial_year(day: date) -> str:
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def chittorgarh_api_urls(url: str, today: date, keep_days: int = 60) -> list[str]:
    """The JSON API URLs behind a chittorgarh yearly report page, or [] for another URL.

    Early in a year we also read last year, so recent IPOs still get their listing results.
    """
    match = _CHITTORGARH_REPORT.match(url)
    if not match:
        return []
    urls = []
    for year in sorted({(today - timedelta(days=keep_days)).year, today.year}):
        day = today if year == today.year else date(year, 12, 31)
        urls.append(
            CHITTORGARH_API.format(
                report_id=match.group(1),
                month=day.month,
                year=year,
                fy=_financial_year(day),
            )
        )
    return urls


# --- Fetching ------------------------------------------------------------------------------


def _get_text(url: str, fetcher: PoliteFetcher) -> str:
    try:
        response = fetcher.get(url)
    except RobotsDisallowed as exc:
        raise IpoSourceError(f"robots.txt does not allow {url}, or it could not be read") from exc
    except httpx.HTTPError as exc:
        raise IpoSourceError(f"{url}: {exc}") from exc

    if response.status_code >= 400:
        raise IpoSourceError(f"{url}: HTTP {response.status_code}")
    return response.text


def fetch_records(
    url: str, fetcher: PoliteFetcher, today: date | None = None, keep_days: int = 60
) -> list[IpoRecord]:
    """Download one page and read the IPOs in it. Raise IpoSourceError if that does not work."""
    api_urls = chittorgarh_api_urls(url, today or date.today(), keep_days)
    if api_urls:
        records = []
        for api_url in api_urls:
            records += parse_ipo_json(_get_text(api_url, fetcher), url)
    else:
        records = parse_ipo_table(_get_text(url, fetcher), url)
    if not records:
        raise IpoSourceError(f"{url}: no IPO table found. The page may have changed.")
    return records
