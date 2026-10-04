from django.db import models


class Ipo(models.Model):
    """An IPO, from announcement to listing."""

    class Category(models.TextChoices):
        MAINBOARD = "mainboard", "Mainboard"
        SME = "sme", "SME"

    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        LISTED = "listed", "Listed"

    name = models.CharField(max_length=200)
    company = models.ForeignKey(
        "companies.Company",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ipos",
    )
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.MAINBOARD)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UPCOMING, db_index=True
    )

    open_date = models.DateField(null=True, blank=True)
    close_date = models.DateField(null=True, blank=True)
    listing_date = models.DateField(null=True, blank=True)

    price_band_low = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_band_high = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    lot_size = models.PositiveIntegerField(null=True, blank=True)
    issue_size_cr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Issue size in crore rupees.",
    )

    gmp = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Grey market premium in rupees.",
    )
    subscription_times = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total subscription, in times.",
    )
    score = models.FloatField(
        null=True,
        blank=True,
        help_text="Our score for this IPO. Set by the scoring step.",
    )

    source_url = models.URLField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-open_date", "name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "open_date"], name="unique_ipo_name_open_date"),
        ]

    def __str__(self):
        return self.name
