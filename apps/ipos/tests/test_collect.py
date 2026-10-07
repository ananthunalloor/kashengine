"""Tests for saving IPOs, the status, and the CSV import."""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.ipos import collect
from apps.ipos.collect import (
    CSV_COLUMNS,
    collect_ipos,
    compute_status,
    expand_urls,
    financial_year,
    find_existing,
    import_csv,
    read_csv,
    refresh_statuses,
    save_record,
)
from apps.ipos.models import Ipo
from apps.ipos.sources import IpoRecord, IpoSourceError

from .helpers import NOW, TODAY, make_ipo

pytestmark = pytest.mark.django_db

D = Decimal


def record(name="Acme Foods Limited", **kwargs) -> IpoRecord:
    kwargs.setdefault("open_date", TODAY)
    return IpoRecord(name=name, **kwargs)


# --- Status --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("open_offset", "close_offset", "listing_offset", "expected"),
    [
        (3, 5, 9, "upcoming"),
        (0, 2, 6, "open"),
        (-1, 0, 4, "open"),  # The last day is still open.
        (-4, -2, 1, "closed"),
        (-8, -6, 0, "listed"),  # The listing day.
        (-8, -6, -1, "listed"),
        (-4, -2, None, "closed"),
        (None, None, None, "upcoming"),
    ],
)
def test_compute_status(open_offset, close_offset, listing_offset, expected):
    def day(offset):
        return None if offset is None else TODAY + timedelta(days=offset)

    ipo = Ipo(
        open_date=day(open_offset), close_date=day(close_offset), listing_date=day(listing_offset)
    )

    assert compute_status(ipo, TODAY) == expected


def test_a_listing_result_means_listed_even_without_a_listing_date():
    assert compute_status(Ipo(listing_gain_pct=5.0), TODAY) == "listed"
    assert compute_status(Ipo(listing_price=D("120")), TODAY) == "listed"


def test_refresh_statuses_changes_status_and_fills_in_the_gain():
    opened = make_ipo("Opened Ltd", open_date=TODAY - timedelta(days=1))
    listed = make_ipo(
        "Listed Ltd",
        open_date=TODAY - timedelta(days=9),
        close_date=TODAY - timedelta(days=7),
        listing_price=D("125"),
        price_band_high=D("100"),
    )
    upcoming = make_ipo("Later Ltd", open_date=TODAY + timedelta(days=4))

    assert refresh_statuses(TODAY) == 2

    for ipo in (opened, listed, upcoming):
        ipo.refresh_from_db()
    assert (opened.status, listed.status, upcoming.status) == ("open", "listed", "upcoming")
    assert listed.listing_gain_pct == pytest.approx(25.0)
    assert refresh_statuses(TODAY) == 0  # A second run changes nothing.


# --- Saving a record -----------------------------------------------------------------------


def test_save_record_creates_an_ipo_with_the_status():
    outcome = save_record(
        record(
            close_date=TODAY + timedelta(days=2),
            price_band_low=D("95"),
            price_band_high=D("100"),
            category="sme",
        ),
        TODAY,
    )

    ipo = Ipo.objects.get()
    assert outcome == "created"
    assert (ipo.status, ipo.category, ipo.price_band_high) == ("open", "sme", D("100"))


def test_save_record_saves_the_exchange_codes_and_keeps_them_when_a_record_has_none():
    save_record(record(nse_symbol="ACME", bse_code="544001", isin="INE000A01010"), TODAY)
    save_record(record(), TODAY)

    ipo = Ipo.objects.get()
    assert (ipo.nse_symbol, ipo.bse_code, ipo.isin) == ("ACME", "544001", "INE000A01010")


def test_save_record_updates_and_does_not_erase_known_values():
    make_ipo(lot_size=150, issue_size_cr=D("500"))

    outcome = save_record(record(price_band_high=D("110")), TODAY)  # No lot size in the record.

    ipo = Ipo.objects.get()
    assert outcome == "updated"
    assert ipo.price_band_high == D("110")
    assert ipo.lot_size == 150
    assert ipo.issue_size_cr == D("500")


def test_save_record_says_unchanged_when_nothing_is_new():
    save_record(record(price_band_high=D("100"), close_date=TODAY + timedelta(days=2)), TODAY)

    again = save_record(
        record(price_band_high=D("100"), close_date=TODAY + timedelta(days=2)), TODAY
    )

    assert again == "unchanged"
    assert Ipo.objects.count() == 1


def test_save_record_skips_an_old_ipo_that_we_do_not_have(settings):
    settings.IPO_KEEP_DAYS = 60
    old = record("Old Ltd", open_date=TODAY - timedelta(days=90))

    assert save_record(old, TODAY) == "skipped"
    assert not Ipo.objects.exists()


def test_an_old_ipo_that_we_have_is_still_updated(settings):
    settings.IPO_KEEP_DAYS = 60
    make_ipo("Old Ltd", open_date=TODAY - timedelta(days=90), close_date=TODAY - timedelta(days=88))

    outcome = save_record(
        record("Old Ltd", open_date=TODAY - timedelta(days=90), listing_gain_pct=12.0), TODAY
    )

    assert outcome == "updated"
    ipo = Ipo.objects.get()
    assert (ipo.status, ipo.listing_gain_pct) == ("listed", 12.0)


def test_an_ipo_that_moves_to_other_dates_is_the_same_ipo():
    first = make_ipo("Acme Foods Limited", open_date=TODAY + timedelta(days=3), close_date=None)

    outcome = save_record(
        record("Acme Foods Ltd.", open_date=TODAY + timedelta(days=10)), TODAY
    )  # Another spelling, new dates.

    assert outcome == "updated"
    assert Ipo.objects.count() == 1
    first.refresh_from_db()
    assert first.open_date == TODAY + timedelta(days=10)
    assert first.name == "Acme Foods Limited"  # We keep the first name.


def test_an_ipo_with_a_result_is_not_matched_to_a_new_ipo_of_the_same_company():
    make_ipo("Acme Foods Limited", open_date=TODAY - timedelta(days=500), listing_gain_pct=3.0)

    assert find_existing(record("Acme Foods Limited", open_date=TODAY)) is None


def test_gmp_and_subscription_from_a_record_set_their_time():
    save_record(record(gmp=D("12"), subscription_times=D("3.5")), TODAY)

    ipo = Ipo.objects.get()
    assert ipo.gmp == D("12")
    assert ipo.subscription_times == D("3.50")
    assert ipo.gmp_updated_at is not None
    assert ipo.subscription_updated_at is not None


def test_the_same_gmp_entered_again_confirms_it():
    save_record(record(gmp=D("12")), TODAY)
    first = Ipo.objects.get().gmp_updated_at

    assert save_record(record(gmp=D("12")), TODAY) == "updated"

    assert Ipo.objects.get().gmp_updated_at > first


# --- The model -----------------------------------------------------------------------------


def test_the_model_sets_the_time_when_the_gmp_changes_in_the_admin():
    ipo = make_ipo()
    assert ipo.gmp_updated_at is None

    ipo.gmp = D("8")
    ipo.save()
    first = ipo.gmp_updated_at
    assert first is not None
    assert ipo.gmp_pct == pytest.approx(8.0)

    ipo.name = "Other name"
    ipo.save()  # The GMP did not change, so the time stays.
    assert ipo.gmp_updated_at == first

    ipo.gmp = D("9")
    ipo.save(update_fields=["gmp"])  # Also works with update_fields.
    ipo.refresh_from_db()
    assert ipo.gmp_updated_at > first


def test_gmp_pct_needs_a_gmp_and_a_price():
    assert Ipo().gmp_pct is None
    assert Ipo(gmp=D("5")).gmp_pct is None
    assert Ipo(gmp=D("-5"), price_band_high=D("100")).gmp_pct == -5.0


# --- Collecting from the source ------------------------------------------------------------


def test_collect_ipos_saves_records_and_reports_failed_pages(monkeypatch):
    def fake_fetch(url, fetcher):
        if "bad" in url:
            raise IpoSourceError(f"{url}: HTTP 503")
        return [record("One Ltd"), record("Two Ltd", open_date=TODAY - timedelta(days=100))]

    monkeypatch.setattr(collect, "fetch_records", fake_fetch)

    stats = collect_ipos(
        fetcher=object(), urls=["https://a.test/good", "https://a.test/bad"], today=TODAY
    )

    assert (stats["created"], stats["skipped"]) == (1, 1)
    assert list(stats["failed"]) == ["https://a.test/bad"]
    assert "HTTP 503" in stats["failed"]["https://a.test/bad"]


# --- CSV -----------------------------------------------------------------------------------

CSV = f"""{CSV_COLUMNS}
Acme Foods Limited,2026-10-05,2026-10-07,2026-10-12,95,100,150,"1,200.5",mainboard,12,,,,https://x.test/a
Tiny Tech,Oct 6 2026,,,,71,,,SME,,2.5,,,
,,,,,,,,,,,,,
"""


def test_read_csv_reads_all_the_columns(tmp_path):
    path = tmp_path / "ipos.csv"
    path.write_text(CSV, encoding="utf-8")

    first, second = read_csv(path)

    assert first.name == "Acme Foods Limited"
    assert first.price_band_low == D("95")
    assert first.lot_size == 150
    assert first.issue_size_cr == D("1200.5")
    assert first.gmp == D("12")
    assert first.subscription_times is None
    assert second.category == "sme"
    assert second.subscription_times == D("2.5")
    assert second.open_date.isoformat() == "2026-10-06"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("open_date\n2026-10-05\n", "name"),
        ("name,gmp\nA Ltd,abc\n", "Line 2: gmp is not a number"),
        ("name,open_date\nA Ltd,someday\n", "Line 2: open_date is not a date"),
        ("name,category\nA Ltd,bluechip\n", "category must be"),
    ],
)
def test_read_csv_rejects_bad_files_with_the_line_number(tmp_path, text, message):
    path = tmp_path / "bad.csv"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        read_csv(path)


def test_import_csv_saves_everything_or_nothing(tmp_path):
    good = tmp_path / "good.csv"
    good.write_text(CSV, encoding="utf-8")
    assert import_csv(good, TODAY) == {"created": 2, "updated": 0, "unchanged": 0, "skipped": 0}

    bad = tmp_path / "bad.csv"
    bad.write_text("name,gmp\nNew One Ltd,5\nBad Ltd,xyz\n", encoding="utf-8")
    with pytest.raises(ValueError):
        import_csv(bad, TODAY)
    assert Ipo.objects.count() == 2  # "New One Ltd" was not saved.


def test_the_now_helper_is_in_india_time():
    assert NOW.utcoffset() == timedelta(hours=5, minutes=30)


def test_the_example_csv_file_is_valid():
    from pathlib import Path

    import apps.ipos

    path = Path(apps.ipos.__file__).parent / "data" / "ipos_example.csv"

    records = read_csv(path)

    assert [r.name for r in records] == [
        "Example Foods Limited",
        "Example Steel Limited",
        "Example Tech Limited",
    ]


# --- Source URLs ---------------------------------------------------------------------------


def test_financial_year():
    from datetime import date

    assert financial_year(date(2026, 10, 5)) == "2026-27"
    assert financial_year(date(2026, 4, 1)) == "2026-27"
    assert financial_year(date(2027, 3, 31)) == "2026-27"
    assert financial_year(date(2099, 12, 1)) == "2099-00"


def test_expand_urls_fills_in_this_month_and_last_month():
    from datetime import date

    url = "https://f.test/data/{month}/{year}/{fy}"

    assert expand_urls([url], date(2026, 10, 5)) == [
        "https://f.test/data/10/2026/2026-27",
        "https://f.test/data/9/2026/2026-27",
    ]
    # In January, last month is December of the year before, in the old financial year.
    assert expand_urls([url], date(2027, 1, 15)) == [
        "https://f.test/data/1/2027/2026-27",
        "https://f.test/data/12/2026/2026-27",
    ]


def test_expand_urls_keeps_a_plain_url_once():
    from datetime import date

    plain = "https://f.test/list"

    assert expand_urls([plain, plain, "https://f.test/other"], date(2026, 10, 5)) == [
        plain,
        "https://f.test/other",
    ]


def test_collect_ipos_reads_the_url_for_each_month(monkeypatch):
    seen = []

    def fake_fetch(url, fetcher):
        seen.append(url)
        return []

    monkeypatch.setattr(collect, "fetch_records", fake_fetch)

    collect_ipos(fetcher=object(), urls=["https://f.test/{month}-{year}"], today=TODAY)

    assert seen == ["https://f.test/10-2026", "https://f.test/9-2026"]
