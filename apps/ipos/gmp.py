"""Read the GMP and the subscription of the open IPOs from a live table.

READ THIS FIRST.
- The fetch is OFF by default (IPO_GMP_ENABLED=false). The default source is the live GMP page of
  investorgain.com. It is a normal HTML page with a static table. robots.txt of the site allows
  it. We found no written permission or ban for automated use, and the site says "All Rights
  Reserved". Read their terms before you turn the fetch on. Use the data for yourself only.
  Do not publish it.
- GMP (grey market premium) is NOT official data. It is a rumour price from a private market.
  The score uses it only when it is fresh, so we keep the time that the SOURCE gives
  ("Updated-On"), not the time of our fetch. If the source stops, our value gets old, and the
  score ignores it.
- We read one page, a few times a day, and we obey robots.txt (PoliteFetcher).
- The table is found by the names of its columns (Name, GMP, Sub, Updated-On). If the page
  changes, the error text lists the columns that we found. Then use `refresh_ipo_data` to see
  the problem. `update_ipo` and `import_ipo_csv` still work as a manual route.
- We tested the parser on sample data made from the column names of the live page. We could not
  test it on the live page from the build server.

A manual entry is never overwritten by an older value from the source: the newer time wins.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
from django.conf import settings
from django.utils import timezone
from lxml import html as lxml_html

from apps.companies.matching import normalize_name
from apps.markets.trading import market_tz
from apps.news.client import make_client
from apps.news.scraper import PoliteFetcher, RobotsDisallowed

from .models import Ipo
from .sources import parse_number

logger = logging.getLogger(__name__)

MIN_PREFIX_CHARS = 6  # A shorter name gives too many false matches.
MAX_GMP_TO_PRICE = 5  # A GMP of more than 5 times the price is a mistake in the source.
SAMPLE_SIZE = 5

# The text right after the rupee sign, up to a space or a bracket. The live page writes a GMP
# that it does not have as "₹-- (0.00%)". The 0.00% is not a GMP, so the text after the sign
# decides.
_RUPEE_TOKEN = re.compile(r"(?:₹|rs\.?)\s*([^\s(]*)", re.IGNORECASE)
_UPDATED = re.compile(
    r"(?P<day>\d{1,2})[-\s/]+(?P<month>[A-Za-z]{3,9})(?:[-\s/,]+(?P<year>\d{2,4}))?"
    r"[\s,]*(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>[AaPp][Mm])?"
)
_MONTHS = {
    name: number
    for number, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        start=1,
    )
}


class GmpSourceError(Exception):
    """We could not read the GMP table."""


@dataclass
class GmpRow:
    name: str
    gmp: Decimal | None
    subscription_times: Decimal | None
    updated_at: datetime | None  # The time that the source gives. None if we cannot read it.


@dataclass
class GmpResult:
    rows: int = 0
    matched: int = 0
    updated: int = 0
    unchanged: int = 0
    older: int = 0  # The source value is older than the value that we have.
    suspect: int = 0  # A GMP that is much too big for the price. We skip it.
    unmatched: list[str] = field(default_factory=list)  # Names that no saved IPO has.

    def as_dict(self) -> dict:
        data = {k: v for k, v in self.__dict__.items() if k != "unmatched"}
        data["unmatched"] = len(self.unmatched)
        return data


# --- Small parsers -------------------------------------------------------------------------


def parse_gmp_value(text: str | None) -> Decimal | None:
    """Read a GMP in rupees. "₹12", "₹ -5", "Rs 7 (3%)" and "12" work.

    "-", "--", and "₹--" give None: the source has no GMP. A real "₹0" gives 0.
    """
    cleaned = (text or "").replace("−", "-").replace("\xa0", " ").strip()
    found = _RUPEE_TOKEN.search(cleaned)
    if found:
        return parse_number(found.group(1))  # None if the token has no digit, like "--".
    if re.fullmatch(r"[-–—\s]*", cleaned):
        return None
    return parse_number(cleaned)


def parse_subscription_value(text: str | None) -> Decimal | None:
    """Read a subscription in times. "52.3x", "0.4 X" and "1,204.5" work."""
    return parse_number((text or "").replace("\xa0", " "))


def parse_updated_on(text: str | None, now: datetime | None = None) -> datetime | None:
    """Read a time like "6-Oct 12:37" (IST). Return None if we cannot read it.

    The year is optional. If it is missing, we use this year, or last year when this year would
    give a time in the future.
    """
    found = _UPDATED.search(text or "")
    if not found:
        return None
    month = _MONTHS.get(found["month"][:3].lower())
    if month is None:
        return None
    tz = market_tz()
    now = (now or timezone.now()).astimezone(tz)
    hour, minute = int(found["hour"]), int(found["minute"])
    if found["ampm"]:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if found["ampm"].lower() == "pm" else 0)
    if hour > 23 or minute > 59:
        return None

    def build(year: int) -> datetime | None:
        try:
            return datetime(year, month, int(found["day"]), hour, minute, tzinfo=tz)
        except ValueError:
            return None

    if found["year"]:
        year = int(found["year"])
        return build(year + 2000 if year < 100 else year)
    stamp = build(now.year)
    if stamp is not None and stamp > now + timedelta(days=1):
        stamp = build(now.year - 1)
    return stamp


def clean_gmp_name(text: str) -> str:
    """Cut the name before the word "IPO". The page adds " IPO" and a status badge."""
    name = " ".join(text.split())
    name = re.split(r"\s+IPO\b", name, maxsplit=1, flags=re.IGNORECASE)[0]
    return name.strip()


# --- The table -----------------------------------------------------------------------------


def _column(headers: list[str], *patterns: str) -> int | None:
    for index, header in enumerate(headers):
        h = " ".join(header.lower().split())
        if any(re.search(pattern, h) for pattern in patterns):
            return index
    return None


def _headers_of(table) -> list[str]:
    cells = table.xpath(".//thead//th") or table.xpath(".//tr[1]/th|.//tr[1]/td")
    return [" ".join(cell.text_content().split()) for cell in cells]


def parse_gmp_table(page: str, now: datetime | None = None) -> list[GmpRow]:
    """Find the GMP table in a page and read its rows.

    The table is the one with a name column and a GMP column. Raise GmpSourceError, with the
    columns that we found, if there is no such table.
    """
    try:
        root = lxml_html.fromstring(page)
    except (ValueError, lxml_html.etree.ParserError) as exc:
        raise GmpSourceError(f"the page is not HTML ({exc})") from exc

    seen: list[list[str]] = []
    for table in root.iter("table"):
        headers = _headers_of(table)
        seen.append(headers)
        name_at = _column(headers, r"^name", r"^ipo$", r"ipo name", r"company")
        gmp_at = _column(headers, r"^gmp")
        if name_at is None or gmp_at is None:
            continue
        sub_at = _column(headers, r"^sub")
        updated_at = _column(headers, r"updated")

        rows = []
        for row in table.xpath(".//tr[td]"):
            cells = row.xpath("./td")
            if len(cells) < len(headers):
                continue  # A note row or a banner row.
            name_cell = cells[name_at]
            anchors = name_cell.xpath(".//a")
            name = clean_gmp_name(
                (anchors[0] if anchors else name_cell).text_content() or name_cell.text_content()
            )
            if not name:
                continue

            def text(index: int | None, cells=cells) -> str:
                return " ".join(cells[index].text_content().split()) if index is not None else ""

            rows.append(
                GmpRow(
                    name=name,
                    gmp=parse_gmp_value(text(gmp_at)),
                    subscription_times=parse_subscription_value(text(sub_at)),
                    updated_at=parse_updated_on(text(updated_at), now),
                )
            )
        if rows:
            return rows
        seen[-1].append("(no rows)")

    found = "; ".join(", ".join(headers) or "(no header)" for headers in seen[:5]) or "no table"
    raise GmpSourceError(f"no GMP table found. The columns that we saw: {found}")


# --- Matching and saving -------------------------------------------------------------------


def _match(key: str, candidates: dict[str, Ipo]) -> Ipo | None:
    """The saved IPO for a source name: the same name, or one name is the start of the other."""
    if key in candidates:
        return candidates[key]
    if len(key) < MIN_PREFIX_CHARS:
        return None
    near = [
        ipo
        for other, ipo in candidates.items()
        if len(other) >= MIN_PREFIX_CHARS
        and (other.startswith(f"{key} ") or key.startswith(f"{other} "))
    ]
    return near[0] if len(near) == 1 else None  # Two possible IPOs: we do not guess.


def apply_gmp_rows(rows: list[GmpRow], now: datetime | None = None) -> GmpResult:
    """Save the GMP and the subscription of the rows into the IPOs that have not listed.

    A value is saved only when the time of the source is newer than the time that we have. We
    save the time of the source. If the source gives no time, we use now.
    """
    now = now or timezone.now()
    result = GmpResult(rows=len(rows))
    candidates = {
        normalize_name(ipo.name): ipo
        for ipo in Ipo.objects.exclude(status=Ipo.Status.LISTED).filter(
            listing_gain_pct__isnull=True
        )
    }
    for row in rows:
        ipo = _match(normalize_name(row.name), candidates)
        if ipo is None:
            result.unmatched.append(row.name)
            continue
        result.matched += 1
        stamp = row.updated_at or now

        fields = []
        if row.gmp is not None:
            limit = (ipo.price_band_high or 0) * MAX_GMP_TO_PRICE
            if limit and abs(row.gmp) > limit:
                logger.warning("GMP of %s looks wrong (%s). We skip it.", ipo.name, row.gmp)
                result.suspect += 1
            elif ipo.gmp_updated_at is None or stamp > ipo.gmp_updated_at:
                ipo.gmp = row.gmp
                ipo.gmp_updated_at = stamp
                fields += ["gmp", "gmp_updated_at"]
            else:
                result.older += 1
        if row.subscription_times is not None and (
            ipo.subscription_updated_at is None or stamp > ipo.subscription_updated_at
        ):
            ipo.subscription_times = row.subscription_times
            ipo.subscription_updated_at = stamp
            fields += ["subscription_times", "subscription_updated_at"]

        if fields:
            ipo.save(update_fields=[*fields, "updated_at"])
            result.updated += 1
        else:
            result.unchanged += 1
    return result


# --- Fetching ------------------------------------------------------------------------------


def fetch_page(url: str, fetcher: PoliteFetcher) -> str:
    try:
        response = fetcher.get(url)
    except RobotsDisallowed as exc:
        raise GmpSourceError(f"robots.txt does not allow {url}, or it could not be read") from exc
    except httpx.HTTPError as exc:
        raise GmpSourceError(f"{url}: {exc}") from exc
    if response.status_code >= 400:
        raise GmpSourceError(f"{url}: HTTP {response.status_code}")
    return response.text


def update_gmp(
    fetcher: PoliteFetcher | None = None,
    url: str | None = None,
    now: datetime | None = None,
    save_page_to: str | Path | None = None,
) -> GmpResult:
    """Download the GMP page and save the numbers. Raise GmpSourceError if that does not work.

    save_page_to: a file path. We write the page there. Use it to send a sample if the parser
    fails.
    """
    url = url or settings.IPO_GMP_URL
    client = None
    if fetcher is None:
        client = make_client()
        fetcher = PoliteFetcher(
            client,
            delay=settings.NEWS_SCRAPE_DELAY_SECONDS,
            user_agent=settings.NEWS_USER_AGENT,
        )
    try:
        page = fetch_page(url, fetcher)
    finally:
        if client is not None:
            client.close()
    if save_page_to:
        Path(save_page_to).write_text(page, encoding="utf-8")
    result = apply_gmp_rows(parse_gmp_table(page, now), now)
    logger.info("GMP update done: %s", result.as_dict())
    return result
