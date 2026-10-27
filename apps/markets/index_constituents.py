"""Refresh official Nifty index constituents from the public NSE Indices CSV files."""

import csv
import io
import re
from dataclasses import dataclass

import httpx
from django.db import transaction

from apps.companies.models import Company
from apps.markets.models import IndexConstituent

INDEXES = (
    ("NIFTY_50", "Nifty 50", "ind_nifty50list.csv"),
    ("NIFTY_NEXT_50", "Nifty Next 50", "ind_niftynext50list.csv"),
    ("NIFTY_100", "Nifty 100", "ind_nifty100list.csv"),
    ("NIFTY_200", "Nifty 200", "ind_nifty200list.csv"),
    ("NIFTY_500", "Nifty 500", "ind_nifty500list.csv"),
    ("NIFTY_MIDCAP_50", "Nifty Midcap 50", "ind_niftymidcap50list.csv"),
    ("NIFTY_MIDCAP_100", "Nifty Midcap 100", "ind_niftymidcap100list.csv"),
    ("NIFTY_MIDCAP_150", "Nifty Midcap 150", "ind_niftymidcap150list.csv"),
    ("NIFTY_SMALLCAP_50", "Nifty Smallcap 50", "ind_niftysmallcap50list.csv"),
    ("NIFTY_SMALLCAP_100", "Nifty Smallcap 100", "ind_niftysmallcap100list.csv"),
    ("NIFTY_SMALLCAP_250", "Nifty Smallcap 250", "ind_niftysmallcap250list.csv"),
)
INDEX_CONSTITUENT_URL = "https://www.niftyindices.com/IndexConstituent/"
MAX_CSV_BYTES = 1_000_000
ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


class IndexConstituentError(Exception):
    """The official index constituent files could not be fetched or validated."""


@dataclass(frozen=True)
class Constituent:
    """A validated symbol and ISIN from one official index list."""

    symbol: str
    isin: str


def _parse_csv(body: bytes) -> list[Constituent]:
    try:
        reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
        if not {"Symbol", "ISIN Code"}.issubset(reader.fieldnames or []):
            raise IndexConstituentError("NSE Indices file is missing required columns.")
        members = []
        seen_symbols = set()
        for row in reader:
            symbol = (row.get("Symbol") or "").strip().upper()
            isin = (row.get("ISIN Code") or "").strip().upper()
            if not symbol or not ISIN_PATTERN.fullmatch(isin) or symbol in seen_symbols:
                raise IndexConstituentError("NSE Indices file contains invalid constituents.")
            seen_symbols.add(symbol)
            members.append(Constituent(symbol=symbol, isin=isin))
    except (UnicodeDecodeError, csv.Error):
        raise IndexConstituentError("NSE Indices file is not valid CSV.") from None
    if not members:
        raise IndexConstituentError("NSE Indices file contains no constituents.")
    return members


def refresh_index_constituents(client: httpx.Client | None = None) -> dict[str, int]:
    """Validate all configured index CSVs, then atomically replace their saved memberships."""
    owns_client = client is None
    client = client or httpx.Client(
        timeout=30,
        follow_redirects=False,
        headers={
            "User-Agent": "KashEngine/1.0",
            "Referer": "https://www.niftyindices.com/",
        },
    )
    try:
        files = {}
        for code, _label, filename in INDEXES:
            try:
                response = client.get(f"{INDEX_CONSTITUENT_URL}{filename}")
            except httpx.HTTPError:
                raise IndexConstituentError(
                    f"Could not download the NSE Indices file for {code}."
                ) from None
            if response.status_code != httpx.codes.OK:
                raise IndexConstituentError(
                    f"NSE Indices returned HTTP {response.status_code} for {code}."
                )
            if len(response.content) > MAX_CSV_BYTES:
                raise IndexConstituentError(f"NSE Indices file for {code} is too large.")
            files[code] = _parse_csv(response.content)
    finally:
        if owns_client:
            client.close()

    isin_to_company = dict(Company.objects.exclude(isin="").values_list("isin", "pk"))
    imported = {}
    with transaction.atomic():
        for code, members in files.items():
            IndexConstituent.objects.filter(index_code=code).delete()
            rows = [
                IndexConstituent(
                    index_code=code,
                    symbol=member.symbol,
                    isin=member.isin,
                    company_id=isin_to_company.get(member.isin),
                )
                for member in members
            ]
            IndexConstituent.objects.bulk_create(rows, batch_size=500)
            imported[code] = len(rows)
    return imported
