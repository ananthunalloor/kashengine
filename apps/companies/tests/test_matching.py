"""Tests for linking news articles to companies."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.companies.matching import CompanyMatcher, link_articles, normalize_name
from apps.companies.models import Company
from apps.news.models import NewsArticle


def test_normalize_name_removes_suffix_words_and_punctuation():
    assert normalize_name("Infosys Ltd.") == "infosys"
    assert normalize_name("Larsen & Toubro Limited") == "larsen & toubro"
    assert normalize_name("Dr Reddy's Laboratories Ltd") == "dr reddy s laboratories"


@pytest.fixture
def companies(db):
    def make(symbol, name, aliases=()):
        return Company.objects.create(symbol=symbol, name=name, aliases=list(aliases))

    return {
        "infy": make("INFY", "Infosys Ltd"),
        "lt": make("LT", "Larsen & Toubro Ltd", ["L&T"]),
        "steel": make("TATASTEEL", "Tata Steel Ltd"),
        "motors": make("TATAMOTORS", "Tata Motors Ltd"),
        "reliance": make("RELIANCE", "Reliance Industries Ltd"),
        "sbi": make("SBIN", "State Bank of India", ["SBI"]),
    }


def ids(matcher: CompanyMatcher, text: str) -> set[int]:
    return matcher.find(text)


def test_name_match_ignores_case_and_suffix(companies):
    matcher = CompanyMatcher()
    assert ids(matcher, "INFOSYS shares rise 3% after results") == {companies["infy"].pk}
    assert ids(matcher, "Shares of Infosys Ltd. rose") == {companies["infy"].pk}


def test_alias_with_ampersand(companies):
    matcher = CompanyMatcher()
    assert ids(matcher, "L&T bags a large order") == {companies["lt"].pk}
    assert ids(matcher, "Larsen & Toubro bags a large order") == {companies["lt"].pk}


def test_longer_name_wins_and_both_companies_are_found(companies):
    matcher = CompanyMatcher()
    found = ids(matcher, "Tata Steel and Tata Motors lead the gainers")
    assert found == {companies["steel"].pk, companies["motors"].pk}


def test_only_whole_words_match(companies):
    matcher = CompanyMatcher()
    assert ids(matcher, "Infosystems launches a new product") == set()
    assert ids(matcher, "Tata Steelworks opens a plant") == set()


def test_symbol_matches_only_in_capital_letters(companies):
    matcher = CompanyMatcher()
    assert ids(matcher, "RELIANCE hits a record high") == {companies["reliance"].pk}
    # "reliance" is a common word. The name is "Reliance Industries", so this is not a match.
    assert ids(matcher, "Heavy reliance on imports hurts the rupee") == set()


def test_short_symbol_is_not_used(companies):
    matcher = CompanyMatcher()
    # The symbol LT has 2 letters. Only the name and the alias find this company.
    assert ids(matcher, "LT rallies") == set()


def test_no_companies_matches_nothing(db):
    assert CompanyMatcher().find("Anything at all") == set()


@pytest.mark.django_db
def test_link_articles_uses_title_and_summary_only_and_is_safe_to_repeat(companies):
    in_title = NewsArticle.objects.create(
        source="T", title="Infosys wins deal", url="https://t.test/1"
    )
    in_summary = NewsArticle.objects.create(
        source="T", title="Sensex today", summary="SBI and L&T lead", url="https://t.test/2"
    )
    in_text_only = NewsArticle.objects.create(
        source="T", title="Market wrap", text="Infosys was also mentioned.", url="https://t.test/3"
    )

    first = link_articles()
    second = link_articles()

    assert first == {"checked": 3, "linked": 2}
    assert second == first
    assert set(in_title.companies.all()) == {companies["infy"]}
    assert set(in_summary.companies.all()) == {companies["sbi"], companies["lt"]}
    assert in_text_only.companies.count() == 0
    assert companies["infy"].news_articles.count() == 1


@pytest.mark.django_db
def test_link_articles_limits_by_age_unless_all(companies):
    old = NewsArticle.objects.create(source="T", title="Infosys old news", url="https://t.test/old")
    NewsArticle.objects.filter(pk=old.pk).update(fetched_at=timezone.now() - timedelta(days=10))

    assert link_articles(since_hours=48) == {"checked": 0, "linked": 0}
    assert link_articles(since_hours=None) == {"checked": 1, "linked": 1}


@pytest.mark.django_db
def test_import_starter_list_and_link_command(capsys):
    call_command("import_companies", "--starter")
    count = Company.objects.count()
    assert count >= 30
    call_command("import_companies", "--starter")  # A second run adds nothing.
    assert Company.objects.count() == count

    article = NewsArticle.objects.create(
        source="T", title="HDFC Bank and State Bank of India shares fall", url="https://t.test/b"
    )
    call_command("link_news")

    assert {c.symbol for c in article.companies.all()} == {"HDFCBANK", "SBIN"}
    assert "1 linked" in capsys.readouterr().out


@pytest.mark.django_db
def test_import_companies_from_a_csv_file(tmp_path):
    csv_file = tmp_path / "companies.csv"
    csv_file.write_text(
        "symbol,name,sector,aliases\n"
        "abc,ABC Industries Ltd,Metals,ABC Steel|ABC Inds\n"
        ",No Symbol Ltd,,\n",
        encoding="utf-8",
    )

    call_command("import_companies", str(csv_file))

    company = Company.objects.get(symbol="ABC")  # The symbol is made upper case.
    assert company.aliases == ["ABC Steel", "ABC Inds"]
    assert company.sector == "Metals"
    assert Company.objects.count() == 1
