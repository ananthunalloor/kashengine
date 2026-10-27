"""Models for the companies app."""

from typing import TYPE_CHECKING, ClassVar

from django.core.validators import RegexValidator
from django.db import models

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager

    from apps.ipos.models import Ipo
    from apps.news.models import NewsArticle


class Company(models.Model):
    """A listed company. Screener.in data is saved here and refreshed on a schedule."""

    name = models.CharField(max_length=200)
    symbol = models.CharField(max_length=50, unique=True, help_text="NSE or BSE symbol.")
    isin = models.CharField(max_length=12, blank=True, db_index=True)
    aliases = models.JSONField(
        default=list,
        blank=True,
        help_text='Other names used in news, for example ["SBI", "State Bank of India"].',
    )
    sector = models.CharField(max_length=100, blank=True)
    upstox_instrument_key = models.CharField(
        max_length=100,
        blank=True,
        validators=[RegexValidator(r"^(NSE_EQ|BSE_EQ)\|[A-Z]{2}[A-Z0-9]{9}[0-9]$")],
        help_text="Exact equity instrument key from Upstox, e.g. NSE_EQ|INE002A01018.",
    )
    upstox_errors = models.JSONField(default=dict, blank=True)
    screener_url = models.URLField(max_length=500, blank=True)
    screener_data = models.JSONField(
        default=dict, blank=True, help_text="Data from Screener.in. Empty until the first refresh."
    )
    last_updated = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the Screener.in data was last fetched. Empty means never.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    if TYPE_CHECKING:
        fundamentals: RelatedManager["CompanyFundamentals"]
        quotes: RelatedManager["CompanyQuote"]
        candles: RelatedManager["CompanyCandle"]
        outlooks: RelatedManager["CompanyOutlook"]
        news_articles: RelatedManager[NewsArticle]
        ipos: RelatedManager[Ipo]

    class Meta:
        ordering: ClassVar[list[str]] = ["name"]
        verbose_name_plural = "companies"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["upstox_instrument_key"],
                condition=~models.Q(upstox_instrument_key=""),
                name="unique_mapped_upstox_company",
            ),
            models.UniqueConstraint(
                fields=["isin"],
                condition=~models.Q(isin=""),
                name="unique_company_isin",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class CompanyFundamentals(models.Model):
    """A dated, reusable Upstox fundamentals snapshot; older snapshots are retained."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="fundamentals")
    instrument_key = models.CharField(max_length=100)
    data = models.JSONField(default=dict)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-fetched_at", "-pk"]

    def __str__(self):
        """Return the company and the time of the copy."""
        return f"{self.company} fundamentals {self.fetched_at}"


class CompanyQuote(models.Model):
    """A persisted quote observation, shared by scheduled REST and streaming ingestion."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="quotes")
    instrument_key = models.CharField(max_length=100)
    as_of = models.DateTimeField()
    price = models.FloatField()
    previous_close = models.FloatField(null=True)
    volume = models.BigIntegerField(null=True)
    mode = models.CharField(max_length=10, choices=[("snapshot", "Snapshot"), ("stream", "Stream")])
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-as_of"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["company", "as_of"], name="unique_company_quote"),
            models.CheckConstraint(condition=models.Q(price__gt=0), name="company_quote_positive"),
        ]

    def __str__(self):
        """Return the company, the time of the quote and the price."""
        return f"{self.company} {self.as_of}: {self.price}"


class CompanyCandle(models.Model):
    """One exchange-local daily OHLCV bar; historical data is incrementally refreshed."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="candles")
    instrument_key = models.CharField(max_length=100)
    day = models.DateField()
    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    close = models.FloatField()
    volume = models.BigIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["day"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["company", "day"], name="unique_company_candle"),
            models.CheckConstraint(condition=models.Q(close__gt=0), name="company_close_positive"),
        ]

    def __str__(self):
        """Return the company, the day and the close."""
        return f"{self.company} {self.day}: {self.close}"


class CompanyOutlook(models.Model):
    """Saved experimental next-session outlook, including its exact inputs and method."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="outlooks")
    target_date = models.DateField()
    direction = models.CharField(max_length=10)
    score = models.FloatField()
    momentum_score = models.FloatField()
    news_score = models.FloatField(null=True)
    inputs = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at", "-pk"]

    def __str__(self):
        """Return the company, the target day and the direction."""
        return f"{self.company} {self.target_date}: {self.direction}"
