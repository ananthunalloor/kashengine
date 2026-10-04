from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Report(models.Model):
    """The daily report. There is one report for each date."""

    class Direction(models.TextChoices):
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Report {self.date}"
