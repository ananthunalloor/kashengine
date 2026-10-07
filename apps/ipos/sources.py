"""Read the IPO list from a source.

READ THIS FIRST.
- The fetch is OFF by default (IPO_FETCH_ENABLED=false). The default source is the IPO list report
  of chittorgarh.com. The page of the report loads its table with JavaScript, so the HTML of the
  page has no table. We read the JSON feed that the page itself uses
  (webnodejs.chittorgarh.com). It is not a documented public API. It can change or stop at any
  time. robots.txt of the host allows it. We found no written permission or ban for automated use,
  and the site says "All rights reserved". Read their terms before you turn the fetch on. Use the
  data for yourself only. Do not publish it.
- We read one or two URLs, one or two times a day, and we obey robots.txt (PoliteFetcher).
- The JSON feed gives dates, price band, and issue size. It does NOT give the GMP (grey market
  premium), the subscription, or the listing result. Enter those with `update_ipo` or
  `import_ipo_csv`. GMP is not official data. Treat it with care.
- A source URL can have {month}, {year}, and {fy} (financial year, like 2026-27). We fill them in
  for this month and for last month (see collect.expand_urls).
- If the feed changes, the run saves nothing, logs a warning, and you can still enter IPOs with
  `import_ipo_csv`, `update_ipo`, or the admin. A source that returns an HTML page is read with a
  table parser that finds the columns by header name.
- We tested the parser on sample data that has the fields of the feed. We could not test it on the
  live service from the build server.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
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
    nse_symbol: str = ""
    bse_code: str = ""
    isin: str = ""
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
    if re.search(r"exchange|platform", h):
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

        records = []
        for row in table.xpath(".//tr[td]"):
            cells = row.xpath("./td")
            if len(cells) < len(headers):
                continue  # A note row or a banner row.

            def text(field: str, cells=cells, columns=columns) -> str:
                index = columns.get(field)
                return " ".join(cells[index].text_content().split()) if index is not None else ""

            name_cell = cells[columns["name"]]
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
    return []


# --- The JSON feed ------------------------------------------------------------------------


def _first(row: dict, *names: str) -> str:
    """The first non-empty text value among some field names."""
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _find_rows(payload) -> list[dict]:
    """Find the list of IPO rows in the JSON. The feed uses the key "reportTableData"."""
    if isinstance(payload, dict):
        rows = payload.get("reportTableData")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        for value in payload.values():
            found = _find_rows(value)
            if found:
                return found
    elif isinstance(payload, list) and payload and all(isinstance(row, dict) for row in payload):
        if any("Company" in row for row in payload):
            return payload
    return []


def parse_ipo_json(payload, source_url: str = "") -> list[IpoRecord]:
    """Read the rows of the JSON feed. Return an empty list if there are no rows.

    A row has the fields "Company" (an HTML link), "Issue Category", "Opening Date",
    "Closing Date", "Listing Date", "Issue Price (Rs.)", and the issue amount in crore rupees.
    A field that is missing or empty gives None.
    """
    records = []
    for row in _find_rows(payload):
        company = _first(row, "Company", "~IPO")
        if not company:
            continue
        cell = lxml_html.fragment_fromstring(company, create_parent="div")
        name = clean_name(cell.text_content())
        if not name:
            continue
        links = cell.xpath(".//a/@href")

        def day(field: str, row=row) -> date | None:
            # Planned dates (fields that start with ~) are not real dates. We do not use them.
            return parse_date(_first(row, field))

        low, high = parse_price_band(_first(row, "Issue Price (Rs.)", "Price Band"))
        records.append(
            IpoRecord(
                name=name,
                open_date=day("Opening Date"),
                close_date=day("Closing Date"),
                listing_date=day("Listing Date"),
                price_band_low=low,
                price_band_high=high,
                issue_size_cr=parse_issue_size_cr(
                    _first(
                        row,
                        "Total Issue Amount (Incl.Firm reservations) (Rs.cr.)",
                        "Issue Amount (Rs.cr.)",
                    )
                ),
                category=SME if "sme" in _first(row, "Issue Category").lower() else MAINBOARD,
                nse_symbol=_first(row, "~nse_symbol").upper(),
                bse_code=_first(row, "~bse_script_code"),
                isin=_first(row, "~isin").upper(),
                source_url=urljoin(source_url, links[0]) if links else source_url,
            )
        )
    return records


# --- Fetching ------------------------------------------------------------------------------


def parse_response(text: str, url: str, content_type: str = "") -> list[IpoRecord]:
    """Read a response as JSON (if it looks like JSON) or as an HTML page."""
    if "json" in content_type.lower() or text.lstrip().startswith(("{", "[")):
        try:
            return parse_ipo_json(json.loads(text), url)
        except (ValueError, TypeError) as exc:
            raise IpoSourceError(f"{url}: the answer is not valid JSON ({exc})") from exc
    return parse_ipo_table(text, url)


def fetch_records(url: str, fetcher: PoliteFetcher) -> list[IpoRecord]:
    """Download one URL and read the IPOs in it. Raise IpoSourceError if that does not work."""
    try:
        response = fetcher.get(url)
    except RobotsDisallowed as exc:
        raise IpoSourceError(f"robots.txt does not allow {url}, or it could not be read") from exc
    except httpx.HTTPError as exc:
        raise IpoSourceError(f"{url}: {exc}") from exc

    if response.status_code >= 400:
        raise IpoSourceError(f"{url}: HTTP {response.status_code}")

    records = parse_response(response.text, url, response.headers.get("content-type", ""))
    if not records:
        raise IpoSourceError(f"{url}: no IPOs found. The source may have changed.")
    return records
