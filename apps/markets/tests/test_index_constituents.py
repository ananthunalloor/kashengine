"""Refresh and validate official index constituent CSVs."""

import httpx
import pytest

from apps.companies.models import Company
from apps.markets.index_constituents import (
    INDEXES,
    IndexConstituentError,
    refresh_index_constituents,
)
from apps.markets.models import IndexConstituent

pytestmark = pytest.mark.django_db


class ConstituentClient:
    def __init__(self, *, failure=None, malformed=False):
        self.failure = failure
        self.malformed = malformed

    def get(self, url):
        if self.failure and url.endswith(self.failure):
            return httpx.Response(503, request=httpx.Request("GET", url))
        csv = "Symbol,Company Name,Industry,ISIN Code\nALPHA,Alpha Company,Finance,INE000A01001\n"
        if self.malformed:
            csv = "unexpected,columns\nnot,a constituent\n"
        return httpx.Response(200, content=csv.encode(), request=httpx.Request("GET", url))


def test_refresh_imports_supported_indexes_and_links_companies_by_isin():
    company = Company.objects.create(
        name="Alpha Company",
        symbol="ALPHA",
        isin="INE000A01001",
    )

    result = refresh_index_constituents(ConstituentClient())

    assert len(result) == len(INDEXES) == 11
    assert set(result.values()) == {1}
    assert IndexConstituent.objects.filter(company=company).count() == len(INDEXES)


@pytest.mark.parametrize(
    "client",
    [
        ConstituentClient(failure="ind_niftysmallcap250list.csv"),
        ConstituentClient(malformed=True),
    ],
)
def test_invalid_refresh_does_not_replace_saved_memberships(client):
    IndexConstituent.objects.create(
        index_code="NIFTY_50",
        symbol="OLD",
        isin="INE000A01001",
    )

    with pytest.raises(IndexConstituentError):
        refresh_index_constituents(client)

    assert list(IndexConstituent.objects.values_list("symbol", flat=True)) == ["OLD"]
