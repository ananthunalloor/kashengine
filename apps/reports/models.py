"""Models for the daily report."""

from typing import ClassVar

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Report(models.Model):
    """The daily report. There is one report for each date.

    `apps.reports.builder.build_report` creates and updates the rows. The `date` field is unique,
    so a build with `force` for the same date replaces the first row. The delivery app sends
    `text`. The web app and the API read `data` and `text`. The ops app checks that the row of
    today exists, and it counts the rows for the metrics.

    `prediction` and `confidence` are copies of the direction and the confidence of the
    `Prediction` row that the report used. The same values are also in `data["prediction"]`.
    """

    class Direction(models.TextChoices):
        """The allowed values of `Report.prediction`: the expected move of the Nifty 50."""

        UP = "up", "Up"
        DOWN = "down", "Down"
        FLAT = "flat", "Flat"

    date = models.DateField(unique=True, help_text="The date of the report.")
    text = models.TextField(blank=True, help_text="The full report text that is sent to users.")
    prediction = models.CharField(max_length=10, choices=Direction.choices, blank=True)
    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="From 0 to 1.",
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="The numbers and the lists behind the text. The web page uses them.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-date"]

    def __str__(self):
        """Return a short label with the date of the report."""
        return f"Report {self.date}"
