from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class IndexQuote(models.Model):
    """The close of one day for an index or a global cue (from Yahoo Finance)."""

    symbol = models.CharField(
        max_length=20, help_text="The Yahoo Finance symbol, for example ^NSEI."
    )
    day = models.DateField(help_text="The trading day. This is the local date of the exchange.")
    close = models.FloatField()
    change_pct = models.FloatField(
        null=True,
        blank=True,
        help_text="Change from the close of the day before, in percent.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When we last saved this row. A row that is older than the close of the "
        "market can hold a price from the middle of the session.",
    )

    class Meta:
        ordering = ["symbol", "-day"]
        constraints = [
            models.UniqueConstraint(fields=["symbol", "day"], name="unique_quote_symbol_day"),
        ]

    def __str__(self):
        return f"{self.symbol} {self.day} {self.close:g}"


class Prediction(models.Model):
    """The prediction for one trading day (Nifty 50), and later the real result."""

    class Direction(models.TextChoices):
        UP = "up", "Up"
        DOWN = "down", "Down"
        FLAT = "flat", "Flat"

    target_date = models.DateField(unique=True, help_text="The trading day that we predict.")
    direction = models.CharField(max_length=10, choices=Direction.choices)
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="How strong the signal is, from 0 to 1. It is NOT a measured probability. "
        "Compare it with the accuracy numbers (python manage.py prediction_stats).",
    )
    score = models.FloatField(help_text="From -1 (down) to 1 (up).")
    news_score = models.FloatField(null=True, blank=True, help_text="Part of the score from news.")
    global_score = models.FloatField(
        null=True, blank=True, help_text="Part of the score from global markets."
    )
    news_articles = models.PositiveIntegerField(default=0, help_text="Articles in the news score.")
    inputs = models.JSONField(
        default=dict, blank=True, help_text="All the numbers that gave this prediction."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # The real result. We fill it in after the market closes.
    actual_change_pct = models.FloatField(null=True, blank=True)
    actual_direction = models.CharField(max_length=10, choices=Direction.choices, blank=True)
    correct = models.BooleanField(
        null=True,
        blank=True,
        help_text="Empty means no result yet, or no trading session on that day.",
    )
    evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-target_date"]

    def __str__(self):
        return f"{self.target_date} {self.direction} ({self.confidence:.2f})"
