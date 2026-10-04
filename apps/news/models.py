from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class NewsArticle(models.Model):
    """One news article from a free source (RSS feed or web page)."""

    source = models.CharField(max_length=100, help_text="Source name, for example Moneycontrol.")
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000, unique=True)
    text = models.TextField(blank=True, help_text="Full article text, if it was scraped.")
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

    class Meta:
        ordering = ["-published_at", "-fetched_at"]

    def __str__(self):
        return self.title
