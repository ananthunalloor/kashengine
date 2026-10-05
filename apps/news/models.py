from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class NewsArticle(models.Model):
    """One news article from a free source (RSS feed or web page)."""

    source = models.CharField(max_length=100, help_text="Source name, for example Moneycontrol.")
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000, unique=True)
    summary = models.TextField(blank=True, help_text="Short text from the RSS feed.")
    text = models.TextField(blank=True, help_text="Full article text, if it was scraped.")
    text_scraped_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When we tried to scrape the full text. Empty means not tried yet.",
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    # Set by the sentiment step. Empty means the article is not scored yet.
    sentiment_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        help_text="From -1 (very negative) to 1 (very positive).",
    )
    sentiment_reason = models.TextField(blank=True)
    relevance = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="How much the article matters to the Indian market, from 0 to 1.",
    )
    sentiment_model = models.CharField(
        max_length=100, blank=True, help_text="The LLM model that scored the article."
    )
    scored_at = models.DateTimeField(
        null=True, blank=True, db_index=True, help_text="Empty means not scored yet."
    )
    sentiment_attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text="Tries that failed. We stop after SENTIMENT_MAX_ATTEMPTS.",
    )

    # Set by apps.companies.matching. It finds company names and symbols in the title and summary.
    companies = models.ManyToManyField(
        "companies.Company",
        blank=True,
        related_name="news_articles",
    )

    class Meta:
        ordering = ["-published_at", "-fetched_at"]

    def __str__(self):
        return self.title
