"""Tests for downloading and refreshing the complete NSE/BSE instrument catalog."""

import gzip
import json

import httpx
import pytest

from apps.companies.models import Company
from apps.markets.instrument_master import InstrumentMasterError, refresh_instruments
from apps.markets.models import MarketInstrument

pytestmark = pytest.mark.django_db


def master_records():
    """Return a representative multi-exchange instrument master."""
    return [
        {
            "instrument_key": "NSE_EQ|INE002A01018",
            "exchange": "NSE",
            "segment": "NSE_EQ",
            "trading_symbol": "RELIANCE",
            "name": "RELIANCE INDUSTRIES LTD",
            "instrument_type": "EQ",
            "isin": "INE002A01018",
            "lot_size": 1,
        },
        {
            "instrument_key": "BSE_EQ|INE002A01018",
            "exchange": "BSE",
            "segment": "BSE_EQ",
            "trading_symbol": "500325",
            "name": "RELIANCE INDUSTRIES LTD",
            "instrument_type": "A",
            "isin": "INE002A01018",
            "lot_size": 1,
        },
        {
            "instrument_key": "NSE_FO|RELIANCE26JUNFUT",
            "exchange": "NSE",
            "segment": "NSE_FO",
            "trading_symbol": "RELIANCE FUT",
            "name": "RELIANCE INDUSTRIES LTD",
            "instrument_type": "FUTSTK",
            "underlying_symbol": "RELIANCE",
            "expiry": 1793125799000,
            "lot_size": 500,
        },
        {
            "instrument_key": "NSE_INDEX|Nifty 50",
            "exchange": "NSE",
            "segment": "NSE_INDEX",
            "trading_symbol": "Nifty 50",
            "name": "Nifty 50",
            "instrument_type": "INDEX",
        },
        {
            "instrument_key": "NCD_FO|USDINR",
            "exchange": "NSE",
            "segment": "NCD_FO",
            "trading_symbol": "USDINR",
            "name": "USDINR",
            "instrument_type": "CE",
        },
        {
            "instrument_key": "BCD_FO|SENSEX",
            "exchange": "BSE",
            "segment": "BCD_FO",
            "trading_symbol": "SENSEX",
            "name": "SENSEX",
            "instrument_type": "CE",
        },
        {
            "instrument_key": "MCX_FO|GOLD",
            "exchange": "MCX",
            "segment": "MCX_FO",
            "trading_symbol": "GOLD",
            "name": "Gold",
            "instrument_type": "FUTCOM",
        },
    ]


class MasterClient:
    def __init__(self, records):
        self.content = gzip.compress(json.dumps(records).encode())

    def get(self, url):
        return httpx.Response(200, content=self.content, request=httpx.Request("GET", url))


def test_refresh_imports_nse_bse_equities_derivatives_and_indices():
    result = refresh_instruments(MasterClient(master_records()))

    company = Company.objects.get(symbol="RELIANCE")
    assert company.name == "RELIANCE INDUSTRIES LTD"
    assert company.isin == "INE002A01018"
    assert company.upstox_instrument_key == ""
    assert company.market_instruments.filter(segment__in=["NSE_EQ", "BSE_EQ"]).count() == 2
    assert company.market_instruments.get(segment="NSE_FO").expiry.isoformat() == "2026-10-27"
    assert result == {
        "instruments": 6,
        "equities": 2,
        "companies_created": 1,
        "instruments_added": 6,
    }
    assert not MarketInstrument.objects.filter(exchange="MCX").exists()


def test_refresh_includes_sme_and_bse_share_series_but_not_funds():
    records = [
        *master_records(),
        {
            "instrument_key": "NSE_EQ|SMECO",
            "exchange": "NSE",
            "segment": "NSE_EQ",
            "trading_symbol": "SMECO",
            "name": "SME COMPANY LTD",
            "instrument_type": "SM",
            "isin": "INE123A01010",
        },
        {
            "instrument_key": "NSE_EQ|BDR",
            "exchange": "NSE",
            "segment": "NSE_EQ",
            "trading_symbol": "BDR",
            "name": "BDR BUILDCON LIMITED",
            "instrument_type": "IT",
            "isin": "INE766Q01014",
        },
        {
            "instrument_key": "NSE_EQ|PERFECT",
            "exchange": "NSE",
            "segment": "NSE_EQ",
            "trading_symbol": "PERFECT",
            "name": "PERFECT INFRAENGINEER LTD",
            "instrument_type": "SZ",
            "isin": "INE925S01012",
        },
        {
            "instrument_key": "BSE_EQ|500001",
            "exchange": "BSE",
            "segment": "BSE_EQ",
            "trading_symbol": "500001",
            "name": "BSE ONLY COMPANY LTD",
            "instrument_type": "X",
            "isin": "INE456B01010",
        },
        {
            "instrument_key": "BSE_EQ|FUND",
            "exchange": "BSE",
            "segment": "BSE_EQ",
            "trading_symbol": "FUND",
            "name": "EXCHANGE TRADED FUND",
            "instrument_type": "E",
            "isin": "INF789C01010",
        },
    ]

    result = refresh_instruments(MasterClient(records))

    assert result["equities"] == 6
    assert Company.objects.count() == 5
    assert Company.objects.get(isin="INE123A01010").symbol == "SMECO"
    assert Company.objects.get(isin="INE766Q01014").symbol == "BDR"
    assert Company.objects.get(isin="INE925S01012").symbol == "PERFECT"
    assert Company.objects.get(isin="INE456B01010").symbol == "500001"
    fund = MarketInstrument.objects.get(instrument_key="BSE_EQ|FUND")
    assert fund.company_id is None


def test_refresh_is_repeatable_and_marks_removed_contracts_inactive():
    first = master_records()
    refresh_instruments(MasterClient(first))
    first.pop(2)

    result = refresh_instruments(MasterClient(first))

    assert result["companies_created"] == 0
    assert result["instruments_added"] == 0
    assert MarketInstrument.objects.get(instrument_key="NSE_FO|RELIANCE26JUNFUT").is_active is False
    assert MarketInstrument.objects.filter(is_active=True).count() == 5


def test_bad_master_does_not_deactivate_saved_instruments():
    refresh_instruments(MasterClient(master_records()))
    invalid = master_records()
    invalid[0]["expiry"] = "not-a-date"

    with pytest.raises(InstrumentMasterError, match="invalid expiry"):
        refresh_instruments(MasterClient(invalid))

    assert MarketInstrument.objects.filter(is_active=True).count() == 6


def test_refresh_attaches_instruments_to_an_existing_company_by_symbol():
    company = Company.objects.create(
        name="Reliance Industries Ltd",
        symbol="RELIANCE",
        upstox_instrument_key="NSE_EQ|INE002A01018",
    )

    refresh_instruments(MasterClient(master_records()))

    assert Company.objects.count() == 1
    company.refresh_from_db()
    assert company.isin == "INE002A01018"
    assert company.upstox_instrument_key == "NSE_EQ|INE002A01018"
    assert company.market_instruments.count() == 3
