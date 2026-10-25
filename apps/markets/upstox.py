"""Store Upstox company data, news and IPO facts independently of page requests."""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import batched
from typing import Literal
from urllib.parse import quote

from django.db import transaction
from django.utils import timezone
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from apps.companies.models import (
    Company,
    CompanyCandle,
    CompanyFundamentals,
    CompanyQuote,
)
from apps.companies.outlook import save_outlook
from apps.ipos.collect import find_existing, save_record
from apps.ipos.models import Ipo
from apps.ipos.sources import IpoRecord
from apps.news.models import NewsArticle
from apps.siteconfig import conf

from .trading import latest_completed_day, market_tz, today_ist
from .upstox_client import UpstoxClient, UpstoxError

logger = logging.getLogger(__name__)
FUNDAMENTALS = (
    "profile",
    "key-ratios",
    "balance-sheet",
    "cash-flow",
    "income-statement",
    "share-holdings",
    "corporate-actions",
)


class ProviderModel(BaseModel):
    """Reject non-finite numbers before they reach storage or scores."""

    model_config = ConfigDict(allow_inf_nan=False)


class Quote(ProviderModel):
    """The documented full quote fields we retain, not the order-book depth."""

    instrument_token: str
    timestamp: datetime
    last_price: float = Field(gt=0)
    ohlc: dict[str, float]
    volume: int = Field(ge=0)


class Story(ProviderModel):
    """News is metadata and summary only; full articles are not scraped."""

    heading: str = Field(min_length=1, max_length=500)
    article_link: str = Field(pattern=r"^https?://", max_length=1000)
    summary: str
    published_time: int = Field(gt=0)


class Issue(ProviderModel):
    """IPO detail fields mapped to the existing IPO lifecycle and scoring engine."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)
    symbol: str = ""
    isin: str = ""
    issue_type: Literal["regular", "sme"]
    minimum_price: Decimal | None = None
    maximum_price: Decimal | None = None
    bidding_start_date: date | None = None
    bidding_end_date: date | None = None
    lot_size: int | None = None
    issue_size: Decimal | None = None
    listing_price: Decimal | None = None
    listing_exchange: str | None = None
    total_subscription: Decimal | None = None
    timeline: dict[str, date | None] = Field(default_factory=dict)


def mapped_companies():
    """Only exact, explicitly configured instrument keys are eligible; never guess symbols."""
    return Company.objects.exclude(upstox_instrument_key="").order_by("pk")


def record_error(company: Company, section: str, error: str = "") -> None:
    """Save or clear the error text of one data part of a company.

    The old good data stays when a part fails. Readers can see which part failed.

    Args:
        company: The company. The object also gets the new `upstox_errors` value.
        section: The part, for example `quotes`, `history` or `fundamentals`.
        error: A safe error text. An empty text clears the error of the part.
    """
    with transaction.atomic():
        saved = Company.objects.select_for_update().get(pk=company.pk)
        errors = dict(saved.upstox_errors)
        if error:
            errors[section] = error
        else:
            errors.pop(section, None)
        company.upstox_errors = errors
        if saved.upstox_errors != errors:
            saved.upstox_errors = errors
            saved.save(update_fields=["upstox_errors"])


def save_quote(company: Company, data: Quote) -> bool:
    """Save one snapshot quote. A quote with the same time is not saved again.

    Args:
        company: The company that the quote should belong to.
        data: The checked quote from Upstox.

    Returns:
        True if a new row was saved, False if a row with the same time existed.

    Raises:
        UpstoxError: If the quote is for another instrument, or its time has no time zone.
    """
    if data.instrument_token != company.upstox_instrument_key:
        raise UpstoxError("Upstox returned a quote for a different instrument.")
    if timezone.is_naive(data.timestamp):
        raise UpstoxError("Upstox returned a quote without a timezone.")
    previous = data.ohlc.get("close")
    _, created = CompanyQuote.objects.get_or_create(
        company=company,
        as_of=data.timestamp,
        defaults={
            "instrument_key": data.instrument_token,
            "price": data.last_price,
            "previous_close": previous if previous and previous > 0 else None,
            "volume": data.volume,
            "mode": "snapshot",
        },
    )
    return created


def sync_quotes(client: UpstoxClient) -> dict:
    """Download snapshot quotes for all Upstox companies, 100 for each request.

    A bad batch or a missing instrument records an error for the company and the work goes on. A
    saved snapshot never replaces a newer quote from the stream.

    Args:
        client: The Upstox client.

    Returns:
        A dict with `saved` (the count of new quotes) and `failed` (a dict from the symbol to a
        safe error text).
    """
    saved = 0
    failed = {}
    for companies in batched(mapped_companies(), 100, strict=False):
        keys = ",".join(company.upstox_instrument_key for company in companies)
        try:
            response = client.get("v2/market-quote/quotes", {"instrument_key": keys})
            values = TypeAdapter(dict[str, Quote]).validate_python(response.data)
            by_key = {value.instrument_token: value for value in values.values()}
        except (UpstoxError, ValidationError) as exc:
            message = (
                str(exc)
                if isinstance(exc, UpstoxError)
                else "Upstox quote batch returned invalid data."
            )
            logger.warning(message)
            for company in companies:
                record_error(company, "quotes", message)
                failed[company.symbol] = message
            continue
        for company in companies:
            try:
                value = by_key.get(company.upstox_instrument_key)
                if value is None:
                    record_error(company, "quotes", "Upstox omitted the requested instrument.")
                    failed[company.symbol] = "Upstox omitted the requested instrument."
                    continue
                saved += save_quote(company, value)
                record_error(company, "quotes")
            except UpstoxError as exc:
                record_error(company, "quotes", str(exc))
                failed[company.symbol] = str(exc)
    return {"saved": saved, "failed": failed}


def sync_history(company: Company, client: UpstoxClient) -> int:
    """Download the daily candles of one company and save the finished days.

    The first run loads one year. Later runs start at the last saved day, so a correction of that
    day is saved. The current day is not saved until its close and the buffer have passed.

    Args:
        company: The company.
        client: The Upstox client.

    Returns:
        The number of candles that were saved or updated.

    Raises:
        UpstoxError: If the answer has a wrong shape or a candle has invalid values.
    """
    latest = (
        company.candles.filter(instrument_key=company.upstox_instrument_key)
        .order_by("-day")
        .first()
    )
    today = today_ist()
    completed = latest_completed_day()
    start = latest.day if latest else today - timedelta(days=365)
    key = quote(company.upstox_instrument_key, safe="")
    response = client.get(f"v3/historical-candle/{key}/days/1/{today}/{start}")
    raw = response.data.get("candles") if isinstance(response.data, dict) else None
    if not isinstance(raw, list):
        raise UpstoxError("Upstox historical candles have an invalid shape.")
    rows = []
    for candle in raw:
        if not isinstance(candle, list) or len(candle) < 6:  # noqa: PLR2004
            raise UpstoxError("Upstox returned an invalid historical candle.")
        stamp = TypeAdapter(datetime).validate_python(candle[0])
        numbers = TypeAdapter(list[float]).validate_python(candle[1:6])
        opening, high, low, close, volume = numbers
        if (
            timezone.is_naive(stamp)
            or not all(0 < value < float("inf") for value in numbers[:4])
            or not 0 <= volume < float("inf")
            or not volume.is_integer()
            or low > min(opening, close)
            or high < max(opening, close)
        ):
            raise UpstoxError("Upstox returned invalid OHLCV values.")
        day = stamp.astimezone(market_tz()).date()
        if start <= day <= completed:
            rows.append(
                CompanyCandle(
                    company=company,
                    instrument_key=company.upstox_instrument_key,
                    day=day,
                    open=opening,
                    high=high,
                    low=low,
                    close=close,
                    volume=int(volume),
                )
            )
    if rows:
        CompanyCandle.objects.bulk_create(
            rows,
            update_conflicts=True,
            unique_fields=["company", "day"],
            update_fields=[
                "instrument_key",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "updated_at",
            ],
        )
        from apps.api.live import publish  # noqa: PLC0415

        publish("companies")
    return len(rows)


def sync_fundamentals(company: Company, client: UpstoxClient) -> bool:
    """Download and save the fundamentals of one company, if the last copy is old enough.

    The function reads all sections (profile, ratios and statements) and saves them together, or
    saves nothing. It also updates the sector of the company from the profile.

    Args:
        company: The company.
        client: The Upstox client.

    Returns:
        True if a new copy was saved. False if the last copy is newer than
        `UPSTOX_FUNDAMENTALS_DAYS` days.

    Raises:
        UpstoxError: If the profile or the key ratios have a wrong shape.
    """
    last = company.fundamentals.filter(instrument_key=company.upstox_instrument_key).first()
    if last and last.fetched_at >= timezone.now() - timedelta(days=conf.UPSTOX_FUNDAMENTALS_DAYS):
        return False
    isin = company.upstox_instrument_key.split("|", 1)[1]
    data = {}
    for section in FUNDAMENTALS:
        params = (
            {"type": "consolidated", "fs": "true"}
            if section in {"balance-sheet", "cash-flow", "income-statement"}
            else None
        )
        data[section] = client.get(f"v2/fundamentals/{quote(isin, safe='')}/{section}", params).data
    profile = data["profile"]
    if not isinstance(profile, dict) or not isinstance(profile.get("company_profile"), str):
        raise UpstoxError("Upstox company profile has an invalid shape.")
    if not isinstance(data["key-ratios"], list):
        raise UpstoxError("Upstox key ratios have an invalid shape.")
    with transaction.atomic():
        CompanyFundamentals.objects.create(
            company=company,
            instrument_key=company.upstox_instrument_key,
            data=data,
        )
        sector = profile.get("sector")
        if isinstance(sector, str):
            company.sector = sector
            company.save(update_fields=["sector"])
    return True


def sync_companies(client: UpstoxClient) -> dict:
    """Update the history and the fundamentals of every Upstox company.

    The two parts are separate. A failure of one part records an error and does not stop the other.
    The function saves the outlook of each company at the end.

    Args:
        client: The Upstox client.

    Returns:
        A dict with `history` (the count of saved candles), `fundamentals` (the count of saved
        copies) and `failed` (a dict from `SYMBOL:section` to a safe error text).
    """
    saved = {"history": 0, "fundamentals": 0}
    failed = {}
    for company in mapped_companies():
        for section, sync in (("history", sync_history), ("fundamentals", sync_fundamentals)):
            try:
                saved[section] += sync(company, client)
                record_error(company, section)
            except (UpstoxError, ValidationError, ValueError) as exc:
                message = (
                    str(exc)
                    if isinstance(exc, UpstoxError)
                    else "Upstox returned invalid company data."
                )
                logger.warning("Upstox %s %s: %s", company.symbol, section, message)
                record_error(company, section, message)
                failed[f"{company.symbol}:{section}"] = message
        save_outlook(company)
    return {**saved, "failed": failed}


def sync_news(client: UpstoxClient) -> dict:
    """Download the news of all Upstox companies and link each article to its company.

    The function reads every page. An article with a known link keeps its sentiment score.

    Args:
        client: The Upstox client.

    Returns:
        A dict with `new`, the count of articles that were not saved before.

    Raises:
        UpstoxError: If a page has invalid data, or Upstox returns an instrument that was not
            requested.
    """
    saved = 0
    for companies in batched(mapped_companies(), 30, strict=False):
        by_key = {company.upstox_instrument_key: company for company in companies}
        for response in client.pages(
            "v2/news",
            {"category": "instrument_keys", "instrument_keys": ",".join(by_key), "page_size": 100},
        ):
            try:
                groups = TypeAdapter(dict[str, list[Story]]).validate_python(response.data)
            except ValidationError:
                raise UpstoxError("Upstox returned invalid news data.") from None
            for key, stories in groups.items():
                if key not in by_key:
                    raise UpstoxError("Upstox news returned an unrequested instrument.")
                for story in stories:
                    article, created = NewsArticle.objects.get_or_create(
                        url=story.article_link,
                        defaults={
                            "source": "Upstox",
                            "title": story.heading,
                            "summary": story.summary,
                            "published_at": datetime.fromtimestamp(
                                story.published_time / 1000, UTC
                            ),
                        },
                    )
                    article.companies.add(by_key[key])
                    saved += created
    return {"new": saved}


def sync_ipos(client: UpstoxClient) -> dict:
    """Download the IPOs of all stages (upcoming, open, closed, listed) and save them.

    The function reads the detail page of each IPO and uses the same save rules as the other IPO
    sources. An IPO with invalid details is skipped and logged.

    Args:
        client: The Upstox client.

    Returns:
        A dict with the counts `created`, `updated`, `unchanged` and `skipped`.

    Raises:
        UpstoxError: If a list or an IPO identifier has a wrong shape.
    """
    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    seen = set()
    for status in ("upcoming", "open", "closed", "listed"):
        for response in client.pages("v2/ipos", {"status": status, "records": 30}):
            if not isinstance(response.data, list):
                raise UpstoxError("Upstox returned an invalid IPO list.")
            for item in response.data:
                issue_id = item.get("id") if isinstance(item, dict) else None
                if not isinstance(issue_id, str):
                    raise UpstoxError("Upstox IPO is missing its identifier.")
                if issue_id in seen:
                    continue
                seen.add(issue_id)
                detail = client.get(f"v2/ipos/{quote(issue_id, safe='')}")
                try:
                    issue = Issue.model_validate(detail.data)
                except ValidationError as exc:
                    fields = ", ".join(
                        f"{'.'.join(str(part) for part in error['loc']) or '<root>'} "
                        f"({error['type']})"
                        for error in exc.errors(include_input=False)
                    )
                    logger.warning("Upstox IPO %s has invalid details at: %s", issue_id, fields)
                    counts["skipped"] += 1
                    continue
                record = IpoRecord(
                    name=issue.name,
                    open_date=issue.bidding_start_date,
                    close_date=issue.bidding_end_date,
                    listing_date=issue.timeline.get("listing_date"),
                    price_band_low=issue.minimum_price or None,
                    price_band_high=issue.maximum_price or None,
                    lot_size=issue.lot_size or None,
                    issue_size_cr=issue.issue_size or None,
                    category=Ipo.Category.SME
                    if issue.issue_type == "sme"
                    else Ipo.Category.MAINBOARD,
                    subscription_times=issue.total_subscription,
                    listing_price=issue.listing_price,
                    nse_symbol=issue.symbol if issue.listing_exchange != "BSE" else "",
                    isin=issue.isin,
                    source_url="https://upstox.com/ipo/",
                )
                with transaction.atomic():
                    existing = Ipo.objects.filter(upstox_id=issue.id).first()
                    if existing:
                        record.name = existing.name
                        record.isin = existing.isin or record.isin
                    counts[save_record(record, upstox_id=issue.id)] += 1
                    ipo = find_existing(record, upstox_id=issue.id)
                    if ipo is not None:
                        ipo.upstox_id = issue.id
                        ipo.upstox_data = detail.data
                        ipo.upstox_updated_at = timezone.now()
                        if ipo.company is None and issue.isin:
                            ipo.company = Company.objects.filter(
                                upstox_instrument_key__in=[
                                    f"NSE_EQ|{issue.isin}",
                                    f"BSE_EQ|{issue.isin}",
                                ],
                            ).first()
                        ipo.save(
                            update_fields=[
                                "upstox_id",
                                "upstox_data",
                                "upstox_updated_at",
                                "company",
                            ]
                        )
    return counts
