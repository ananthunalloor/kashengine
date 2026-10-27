"""Refresh the exchange instrument catalog from Upstox's public daily master."""

import gzip
import json
import zlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from zoneinfo import ZoneInfo

import httpx
from django.db import transaction

from apps.companies.models import Company
from apps.markets.models import MarketInstrument

INSTRUMENT_MASTER_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
)
MAX_COMPRESSED_BYTES = 30_000_000
MAX_UNCOMPRESSED_BYTES = 150_000_000
NSE_SHARE_SERIES = {"BE", "BZ", "EQ", "IT", "SM", "ST", "SZ"}
BSE_SHARE_SERIES = {"A", "B", "M", "MS", "MT", "P", "T", "TS", "X", "XT", "Z", "ZP"}
FIELD_LIMITS = {
    "instrument_key": 100,
    "trading_symbol": 100,
    "name": 200,
    "instrument_type": 30,
    "segment": 20,
    "isin": 12,
    "underlying_symbol": 100,
}
IST = ZoneInfo("Asia/Kolkata")
MIN_EXPIRY_TIMESTAMP_MS = 1_000_000_000_000


class InstrumentMasterError(Exception):
    """The exchange master could not be fetched or validated in full."""


@dataclass(frozen=True)
class MasterRecord:
    """A validated Upstox master entry for an NSE or BSE instrument."""

    instrument_key: str
    exchange: str
    segment: str
    trading_symbol: str
    name: str
    instrument_type: str
    isin: str
    underlying_symbol: str
    expiry: date | None
    strike_price: Decimal | None
    lot_size: int | None


def _is_company_share(record: MasterRecord) -> bool:
    """Recognize company-share series; debt, funds and other cash instruments stay catalog-only."""
    return (record.segment == "NSE_EQ" and record.instrument_type in NSE_SHARE_SERIES) or (
        record.segment == "BSE_EQ" and record.instrument_type in BSE_SHARE_SERIES
    )


def _company_for_record(
    record: MasterRecord,
    identity: str,
    share_companies: dict[str, Company],
    companies_by_symbol: dict[str, Company],
) -> Company | None:
    if _is_company_share(record):
        return share_companies.get(identity)
    if record.segment in {"NSE_FO", "BSE_FO", "NCD_FO", "BCD_FO"}:
        return companies_by_symbol.get(record.underlying_symbol[:50])
    return None


def _read_master(client: httpx.Client | None = None) -> bytes:
    """Download and bounded-decompress the current official instrument master."""
    owns_client = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=False)
    try:
        try:
            response = client.get(INSTRUMENT_MASTER_URL)
        except httpx.HTTPError:
            raise InstrumentMasterError(
                "Could not download the Upstox instrument master."
            ) from None
        if response.status_code != httpx.codes.OK:
            raise InstrumentMasterError(
                f"Upstox instrument master returned HTTP {response.status_code}."
            )
        if len(response.content) > MAX_COMPRESSED_BYTES:
            raise InstrumentMasterError("Upstox instrument master is larger than expected.")
        try:
            with gzip.GzipFile(fileobj=BytesIO(response.content)) as compressed:
                body = compressed.read(MAX_UNCOMPRESSED_BYTES + 1)
        except (gzip.BadGzipFile, EOFError, OSError, zlib.error):
            raise InstrumentMasterError(
                "Upstox instrument master is not valid gzip data."
            ) from None
        if len(body) > MAX_UNCOMPRESSED_BYTES:
            raise InstrumentMasterError("Upstox instrument master is larger than expected.")
        return body
    finally:
        if owns_client:
            client.close()


def _parse_expiry(value: object) -> date | None:
    """Parse the provider's optional ISO date or millisecond timestamp as an IST date."""
    if value is None or value == "":
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value == 0:
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise InstrumentMasterError(
                "Upstox instrument master contains an invalid expiry."
            ) from None
    if isinstance(value, int) and not isinstance(value, bool) and value >= MIN_EXPIRY_TIMESTAMP_MS:
        try:
            return datetime.fromtimestamp(value / 1000, tz=UTC).astimezone(IST).date()
        except (OverflowError, OSError, ValueError):
            raise InstrumentMasterError(
                "Upstox instrument master contains an invalid expiry."
            ) from None
    else:
        raise InstrumentMasterError("Upstox instrument master contains an invalid expiry.")


def _parse_strike(value: object) -> Decimal | None:
    """Parse an optional finite strike price."""
    try:
        strike = Decimal(str(value)) if value is not None else None
    except (InvalidOperation, ValueError):
        raise InstrumentMasterError(
            "Upstox instrument master contains an invalid strike."
        ) from None
    if strike is not None and not strike.is_finite():
        raise InstrumentMasterError("Upstox instrument master contains an invalid strike.")
    return strike


def _parse_lot_size(value: object) -> int | None:
    """Parse a positive integral lot size."""
    if value is None:
        return None
    try:
        decimal = Decimal(str(value))
        lot_size = int(decimal)
    except (InvalidOperation, OverflowError, TypeError, ValueError):
        raise InstrumentMasterError(
            "Upstox instrument master contains an invalid lot size."
        ) from None
    if Decimal(lot_size) != decimal:
        raise InstrumentMasterError("Upstox instrument master contains an invalid lot size.")
    return lot_size if lot_size > 0 else None


def _parse_record(row: dict) -> MasterRecord | None:
    """Validate one provider object and ignore instruments outside NSE and BSE."""
    exchange = row.get("exchange")
    if exchange not in {"NSE", "BSE"}:
        return None
    segment = row.get("segment")
    exchange_prefix = f"{exchange}_"
    currency_segment = {"NSE": "NCD_FO", "BSE": "BCD_FO"}[exchange]
    if not isinstance(segment, str) or (
        not segment.startswith(exchange_prefix) and segment != currency_segment
    ):
        raise InstrumentMasterError("Upstox instrument master contains an invalid segment.")
    values = {
        key: row.get(key, "")
        for key in ("instrument_key", "trading_symbol", "name", "instrument_type")
    }
    if any(not isinstance(value, str) or not value.strip() for value in values.values()):
        raise InstrumentMasterError("Upstox instrument master contains missing identifiers.")
    if any(
        len(value) > FIELD_LIMITS[field] for field, value in {**values, "segment": segment}.items()
    ):
        raise InstrumentMasterError("Upstox instrument master contains oversized fields.")
    isin = row.get("isin") or ""
    underlying = row.get("underlying_symbol") or ""
    if not isinstance(isin, str) or len(isin) > FIELD_LIMITS["isin"]:
        raise InstrumentMasterError("Upstox instrument master contains an invalid ISIN.")
    if not isinstance(underlying, str) or len(underlying) > FIELD_LIMITS["underlying_symbol"]:
        raise InstrumentMasterError(
            "Upstox instrument master contains an invalid underlying symbol."
        )
    raw_expiry = row.get("expiry")
    return MasterRecord(
        instrument_key=values["instrument_key"],
        exchange=exchange,
        segment=segment,
        trading_symbol=values["trading_symbol"],
        name=values["name"],
        instrument_type=values["instrument_type"],
        isin=isin,
        underlying_symbol=underlying,
        expiry=_parse_expiry(raw_expiry),
        strike_price=_parse_strike(row.get("strike_price")),
        lot_size=_parse_lot_size(row.get("lot_size")),
    )


def _parse_master(body: bytes) -> list[MasterRecord]:
    """Parse every NSE/BSE record; reject malformed provider data before saving anything."""
    try:
        raw_records = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise InstrumentMasterError("Upstox instrument master is not valid JSON.") from None
    if not isinstance(raw_records, list) or not raw_records:
        raise InstrumentMasterError("Upstox instrument master has no instrument records.")

    records = []
    seen_keys = set()
    for row in raw_records:
        if not isinstance(row, dict):
            raise InstrumentMasterError("Upstox instrument master contains an invalid record.")
        record = _parse_record(row)
        if record is None:
            continue
        if record.instrument_key in seen_keys:
            raise InstrumentMasterError(
                "Upstox instrument master contains duplicate instrument keys."
            )
        seen_keys.add(record.instrument_key)
        records.append(record)
    if not records:
        raise InstrumentMasterError("Upstox instrument master contains no NSE or BSE records.")
    return records


def _company_symbol(candidate: str, isin: str, occupied: set[str]) -> str:
    """Keep the preferred trading symbol unless another ISIN already owns it."""
    symbol = candidate[:50]
    if symbol not in occupied:
        return symbol
    base_suffix = f"-{isin[-4:]}" if isin else "-BSE"
    suffix = base_suffix
    attempt = 1
    while True:
        resolved = f"{symbol[: 50 - len(suffix)]}{suffix}"
        if resolved not in occupied:
            return resolved
        attempt += 1
        suffix = f"{base_suffix}-{attempt}"


def refresh_instruments(client: httpx.Client | None = None) -> dict[str, int]:
    """Atomically refresh NSE/BSE instruments and link equity listings to companies.

    The company identity is an ISIN when the source provides one. Its primary display symbol
    prefers NSE, while each provider key remains attached to its exact exchange instrument. The
    refresh does not automatically enable quote streaming or fundamentals ingestion.
    """
    records = _parse_master(_read_master(client))
    share_records = [record for record in records if _is_company_share(record)]
    share_groups: dict[str, list[MasterRecord]] = {}
    for record in share_records:
        identity = f"isin:{record.isin}" if record.isin else f"key:{record.instrument_key}"
        share_groups.setdefault(identity, []).append(record)

    with transaction.atomic():
        existing_keys = set(
            MarketInstrument.objects.filter(exchange__in=["NSE", "BSE"]).values_list(
                "instrument_key", flat=True
            )
        )
        MarketInstrument.objects.filter(exchange__in=["NSE", "BSE"]).update(is_active=False)
        company_by_isin = {
            company.isin: company
            for company in Company.objects.filter(
                isin__in=[record.isin for record in share_records if record.isin]
            )
        }
        candidate_symbols = {record.trading_symbol[:50] for record in share_records}
        company_by_symbol = {
            company.symbol: company
            for company in Company.objects.filter(symbol__in=candidate_symbols)
        }
        keys = {record.instrument_key for record in share_records}
        company_by_key = {
            company.upstox_instrument_key: company
            for company in Company.objects.filter(upstox_instrument_key__in=keys)
        }
        occupied = set(Company.objects.values_list("symbol", flat=True))
        group_company: dict[str, Company] = {}
        created_companies = 0

        for identity, group in share_groups.items():
            preferred = min(
                group,
                key=lambda record: (record.exchange != "NSE", record.trading_symbol),
            )
            company = company_by_isin.get(preferred.isin) if preferred.isin else None
            if company is None:
                company = next(
                    (
                        company_by_key[record.instrument_key]
                        for record in group
                        if record.instrument_key in company_by_key
                    ),
                    None,
                )
            if company is None:
                company = next(
                    (
                        company_by_symbol[record.trading_symbol[:50]]
                        for record in group
                        if record.trading_symbol[:50] in company_by_symbol
                    ),
                    None,
                )

            if (
                company is not None
                and company.isin
                and preferred.isin
                and company.isin != preferred.isin
            ):
                company = None
            if company is None:
                symbol = _company_symbol(preferred.trading_symbol, preferred.isin, occupied)
                company = Company.objects.create(
                    name=preferred.name[:200],
                    symbol=symbol,
                    isin=preferred.isin,
                )
                occupied.add(symbol)
                created_companies += 1
            else:
                changed_fields = []
                if preferred.isin and not company.isin:
                    company.isin = preferred.isin
                    changed_fields.append("isin")
                if changed_fields:
                    company.save(update_fields=changed_fields)
            group_company[identity] = company
            if preferred.isin:
                company_by_isin[preferred.isin] = company
            company_by_key.update({record.instrument_key: company for record in group})
            company_by_symbol.update({record.trading_symbol[:50]: company for record in group})

        instruments = []
        for record in records:
            identity = f"isin:{record.isin}" if record.isin else f"key:{record.instrument_key}"
            company = _company_for_record(record, identity, group_company, company_by_symbol)
            instruments.append(
                MarketInstrument(
                    instrument_key=record.instrument_key,
                    exchange=record.exchange,
                    segment=record.segment,
                    trading_symbol=record.trading_symbol,
                    name=record.name,
                    instrument_type=record.instrument_type,
                    isin=record.isin,
                    underlying_symbol=record.underlying_symbol,
                    expiry=record.expiry,
                    strike_price=record.strike_price,
                    lot_size=record.lot_size,
                    company=company,
                )
            )
        MarketInstrument.objects.bulk_create(
            instruments,
            batch_size=1000,
            update_conflicts=True,
            unique_fields=["instrument_key"],
            update_fields=[
                "exchange",
                "segment",
                "trading_symbol",
                "name",
                "instrument_type",
                "isin",
                "underlying_symbol",
                "expiry",
                "strike_price",
                "lot_size",
                "is_active",
                "refreshed_at",
                "company",
            ],
        )

    return {
        "instruments": len(instruments),
        "equities": len(share_records),
        "companies_created": created_companies,
        "instruments_added": len({record.instrument_key for record in records} - existing_keys),
    }
