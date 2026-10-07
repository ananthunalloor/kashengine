"""Save IPOs from a source or a CSV file. Keep the status and the listing result up to date."""

import csv
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.companies.matching import normalize_name
from apps.markets.trading import today_ist
from apps.news.client import make_client
from apps.news.scraper import PoliteFetcher

from .models import Ipo
from .sources import MAINBOARD, SME, IpoRecord, IpoSourceError, fetch_records, parse_date

logger = logging.getLogger(__name__)

# Fields that a record can set. A value of None never replaces a value that we have.
PLAIN_FIELDS = (
    "open_date",
    "close_date",
    "listing_date",
    "price_band_low",
    "price_band_high",
    "lot_size",
    "issue_size_cr",
    "listing_price",
    "listing_gain_pct",
    "nse_symbol",
    "bse_code",
    "isin",
    "source_url",
)


def compute_status(ipo: Ipo, today: date) -> str:
    """The status that the dates give. We have no calendar of holidays, so the dates rule."""
    if ipo.listing_gain_pct is not None or ipo.listing_price is not None:
        return Ipo.Status.LISTED
    if ipo.listing_date and today >= ipo.listing_date:
        return Ipo.Status.LISTED
    if ipo.close_date and today > ipo.close_date:
        return Ipo.Status.CLOSED
    if ipo.open_date and today >= ipo.open_date:
        return Ipo.Status.OPEN
    return Ipo.Status.UPCOMING


def listing_gain_from_price(ipo: Ipo) -> float | None:
    """The gain at the listing, from the listing price and the upper price band."""
    if ipo.listing_price is None or not ipo.price_band_high:
        return None
    return float((ipo.listing_price / ipo.price_band_high - 1) * 100)


def refresh_statuses(today: date | None = None) -> int:
    """Set the status of every IPO from its dates. Fill in a missing listing gain.

    Return the number of IPOs that changed.
    """
    today = today or today_ist()
    changed = 0
    for ipo in Ipo.objects.exclude(status=Ipo.Status.LISTED, listing_gain_pct__isnull=False):
        fields = []
        if ipo.listing_gain_pct is None:
            gain = listing_gain_from_price(ipo)
            if gain is not None:
                ipo.listing_gain_pct = gain
                fields.append("listing_gain_pct")
        status = compute_status(ipo, today)
        if status != ipo.status:
            ipo.status = status
            fields.append("status")
        if fields:
            ipo.save(update_fields=[*fields, "updated_at"])
            changed += 1
    return changed


def find_existing(record: IpoRecord) -> Ipo | None:
    """Find the saved IPO that a record is about.

    1. The same name and the same open date.
    2. The same company (the name without "Ltd" and so on) with no result yet. This covers an IPO
       that moved to other dates. A company does not make two IPOs at the same time.
    """
    exact = Ipo.objects.filter(name=record.name, open_date=record.open_date).first()
    if exact:
        return exact
    key = normalize_name(record.name)
    if not key:
        return None
    candidates = [ipo for ipo in Ipo.objects.all() if normalize_name(ipo.name) == key]
    for ipo in candidates:
        if ipo.open_date == record.open_date:
            return ipo
    pending = [
        ipo for ipo in candidates if ipo.listing_gain_pct is None and ipo.listing_price is None
    ]
    return pending[0] if pending else None


def save_record(record: IpoRecord, today: date | None = None) -> str:
    """Save one record. Return "created", "updated", "unchanged", or "skipped"."""
    today = today or today_ist()
    ipo = find_existing(record)

    if ipo is None:
        oldest = today - timedelta(days=settings.IPO_KEEP_DAYS)
        if record.open_date and record.open_date < oldest:
            return "skipped"  # An old IPO. We have no score for it, so it is no use to us.
        ipo = Ipo(name=record.name, category=record.category or MAINBOARD)
        outcome = "created"
    else:
        outcome = "updated"

    tracked = (*PLAIN_FIELDS, "listing_gain_pct", "status")
    before = {field: getattr(ipo, field) for field in tracked}
    for field in PLAIN_FIELDS:
        value = getattr(record, field)
        if value not in (None, ""):
            setattr(ipo, field, value)

    now = timezone.now()
    if record.gmp is not None:
        ipo.gmp = record.gmp
        ipo.gmp_updated_at = now  # An entry confirms the value, also when it did not change.
    if record.subscription_times is not None:
        ipo.subscription_times = record.subscription_times
        ipo.subscription_updated_at = now
    if record.category and outcome == "created":
        ipo.category = record.category

    if ipo.listing_gain_pct is None:
        ipo.listing_gain_pct = listing_gain_from_price(ipo)
    ipo.status = compute_status(ipo, today)

    after = {field: getattr(ipo, field) for field in tracked}
    entered_metric = record.gmp is not None or record.subscription_times is not None
    if outcome == "updated" and after == before and not entered_metric:
        return "unchanged"
    ipo.save()
    return outcome


def financial_year(day: date) -> str:
    """The Indian financial year of a day, like "2026-27". It starts on 1 April."""
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def expand_urls(urls, today: date) -> list[str]:
    """Fill in {month}, {year}, and {fy} in the source URLs, for this month and last month.

    A URL without these marks is used as it is. The same URL is used once.
    """
    first_of_month = today.replace(day=1)
    months = [first_of_month, (first_of_month - timedelta(days=1)).replace(day=1)]
    expanded: list[str] = []
    for url in urls:
        if not any(mark in url for mark in ("{month}", "{year}", "{fy}")):
            candidates = [url]
        else:
            candidates = [
                url.replace("{month}", str(m.month))
                .replace("{year}", str(m.year))
                .replace("{fy}", financial_year(m))
                for m in months
            ]
        expanded.extend(c for c in candidates if c not in expanded)
    return expanded


def collect_ipos(
    fetcher: PoliteFetcher | None = None, urls=None, today: date | None = None
) -> dict:
    """Read the source pages and save the IPOs. A page that fails does not stop the others.

    Return {"created", "updated", "unchanged", "skipped", "failed": {url: error text}}.
    """
    stats = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "failed": {}}
    today = today or today_ist()
    urls = expand_urls(settings.IPO_SOURCE_URLS if urls is None else urls, today)

    client = None
    if fetcher is None:
        client = make_client()
        fetcher = PoliteFetcher(
            client,
            delay=settings.NEWS_SCRAPE_DELAY_SECONDS,
            user_agent=settings.NEWS_USER_AGENT,
        )
    try:
        for url in urls:
            try:
                records = fetch_records(url, fetcher)
            except IpoSourceError as exc:
                logger.warning("IPO source failed: %s", exc)
                stats["failed"][url] = str(exc)
                continue
            for record in records:
                stats[save_record(record, today)] += 1
    finally:
        if client is not None:
            client.close()
    logger.info("IPO collection done: %s", stats)
    return stats


# --- CSV -----------------------------------------------------------------------------------

CSV_COLUMNS = (
    "name,open_date,close_date,listing_date,price_band_low,price_band_high,lot_size,"
    "issue_size_cr,category,gmp,subscription_times,listing_price,listing_gain_pct,source_url"
)


def _decimal(value: str, column: str, line: int) -> Decimal | None:
    value = (value or "").strip().replace(",", "")
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Line {line}: {column} is not a number: {value!r}") from exc


def _date(value: str, column: str, line: int) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError(f"Line {line}: {column} is not a date: {value!r}")
    return parsed


def read_csv(path: str | Path) -> list[IpoRecord]:
    """Read IPO records from a CSV file. The first line names the columns.

    Only "name" is required. Empty cells mean "not known" and do not change a saved value.
    Raise ValueError (with the line number) for a bad value. Nothing is saved then.
    """
    records = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "name" not in [f.strip() for f in reader.fieldnames]:
            raise ValueError('The first line must name the columns, and "name" is required.')
        for line, row in enumerate(reader, start=2):
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            name = row.get("name", "")
            if not name:
                continue
            category = row.get("category", "").lower()
            if category and category not in (MAINBOARD, SME):
                raise ValueError(f"Line {line}: category must be mainboard or sme: {category!r}")
            lot = _decimal(row.get("lot_size", ""), "lot_size", line)
            gain = _decimal(row.get("listing_gain_pct", ""), "listing_gain_pct", line)
            records.append(
                IpoRecord(
                    name=name,
                    open_date=_date(row.get("open_date", ""), "open_date", line),
                    close_date=_date(row.get("close_date", ""), "close_date", line),
                    listing_date=_date(row.get("listing_date", ""), "listing_date", line),
                    price_band_low=_decimal(row.get("price_band_low", ""), "price_band_low", line),
                    price_band_high=_decimal(
                        row.get("price_band_high", ""), "price_band_high", line
                    ),
                    lot_size=int(lot) if lot else None,
                    issue_size_cr=_decimal(row.get("issue_size_cr", ""), "issue_size_cr", line),
                    category=category or None,
                    gmp=_decimal(row.get("gmp", ""), "gmp", line),
                    subscription_times=_decimal(
                        row.get("subscription_times", ""), "subscription_times", line
                    ),
                    listing_price=_decimal(row.get("listing_price", ""), "listing_price", line),
                    listing_gain_pct=float(gain) if gain is not None else None,
                    source_url=row.get("source_url", ""),
                )
            )
    return records


def import_csv(path: str | Path, today: date | None = None) -> dict:
    """Save all the records of a CSV file. Return the same counts as collect_ipos."""
    stats = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    for record in read_csv(path):
        stats[save_record(record, today)] += 1
    return stats


__all__ = [
    "CSV_COLUMNS",
    "collect_ipos",
    "compute_status",
    "expand_urls",
    "find_existing",
    "import_csv",
    "read_csv",
    "refresh_statuses",
    "save_record",
]
