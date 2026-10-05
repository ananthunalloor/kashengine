"""Find company names and symbols in news articles and link the articles to the companies.

Rules (simple on purpose, to keep false matches low):
- We search the title and the summary. We do not search the full text, because a long article
  often names other companies only in passing.
- A company name or alias matches as whole words, in any letter case. We remove "Ltd",
  "Limited", and similar words from the name first: "Infosys Ltd" matches "Infosys".
- A symbol matches only when it is written in capital letters, as whole words, and has 3 or more
  characters: "RELIANCE" matches the symbol RELIANCE. "reliance" does not, because it is a
  common word.
- To catch a name that the news writes in a different way, add it to the company aliases.
  Do not use a common word as an alias, because aliases match in any letter case.
"""

import logging
import re
from datetime import timedelta

from django.utils import timezone

from apps.news.models import NewsArticle

from .models import Company

logger = logging.getLogger(__name__)

MIN_TERM_LENGTH = 3
# Words that do not belong to the name of a company.
NAME_SUFFIXES = {"ltd", "limited", "inc", "corp", "corporation", "co", "company", "pvt", "private"}


def normalize_text(text: str) -> str:
    """Remove punctuation and extra spaces. We keep "&", so "L&T" stays one word."""
    return " ".join(re.sub(r"[^\w&\s]", " ", text).split())


def normalize_name(name: str) -> str:
    """Make a lower-case name without punctuation and without words like "Ltd"."""
    words = normalize_text(name.lower()).split()
    while words and words[-1] in NAME_SUFFIXES:
        words.pop()
    return " ".join(words)


def _word_pattern(terms, flags: int = 0) -> re.Pattern | None:
    """One pattern for many terms, as whole words. Longer terms go first."""
    ordered = sorted(set(terms), key=len, reverse=True)
    if not ordered:
        return None
    body = "|".join(re.escape(term) for term in ordered)
    return re.compile(rf"(?<![\w&])(?:{body})(?![\w&])", flags)


class CompanyMatcher:
    """Find the companies that a text names."""

    def __init__(self, companies=None):
        companies = Company.objects.all() if companies is None else companies
        self._by_name: dict[str, set[int]] = {}
        self._by_symbol: dict[str, set[int]] = {}
        for company in companies:
            for name in [company.name, *(company.aliases or [])]:
                term = normalize_name(str(name))
                if len(term) >= MIN_TERM_LENGTH:
                    self._by_name.setdefault(term, set()).add(company.pk)
            symbol = company.symbol.strip()
            if len(symbol) >= MIN_TERM_LENGTH and symbol.isupper():
                self._by_symbol.setdefault(symbol, set()).add(company.pk)

        self._name_re = _word_pattern(self._by_name, re.IGNORECASE)
        self._symbol_re = _word_pattern(self._by_symbol)  # Case sensitive.

    def find(self, text: str) -> set[int]:
        """Return the IDs of the companies that the text names."""
        found: set[int] = set()
        if self._name_re:
            for match in self._name_re.finditer(normalize_text(text)):
                found |= self._by_name[match.group(0).lower()]
        if self._symbol_re:
            for match in self._symbol_re.finditer(text):
                found |= self._by_symbol[match.group(0)]
        return found


def link_articles(articles=None, since_hours: int | None = 48) -> dict:
    """Link articles to the companies that they name. Safe to run again.

    Pass `articles` to link a given set. Otherwise, link the articles that we fetched in the
    last `since_hours` hours. With since_hours=None, link all articles.
    """
    matcher = CompanyMatcher()
    if articles is None:
        articles = NewsArticle.objects.all()
        if since_hours is not None:
            cutoff = timezone.now() - timedelta(hours=since_hours)
            articles = articles.filter(fetched_at__gte=cutoff)

    checked = linked = 0
    for article in articles.iterator():
        checked += 1
        ids = matcher.find(f"{article.title}. {article.summary}")
        if ids:
            article.companies.add(*ids)
            linked += 1
    logger.info("Company linking: %d articles checked, %d linked", checked, linked)
    return {"checked": checked, "linked": linked}
