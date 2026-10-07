from django.db import models
from django.utils import timezone


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
    gmp_updated_at = models.DateTimeField(
        null=True, blank=True, help_text="When the GMP was last set or confirmed."
    )
    subscription_updated_at = models.DateTimeField(
        null=True, blank=True, help_text="When the subscription was last set or confirmed."
    )

    # The result. We fill it in after the listing.
    listing_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, help_text="Price at the listing."
    )
    listing_gain_pct = models.FloatField(
        null=True,
        blank=True,
        help_text="Gain at the listing, in percent, compared with the upper price band.",
    )

    # Set by the scoring step (apps/ipos/scoring.py).
    class Verdict(models.TextChoices):
        GOOD = "good", "Likely to do well"
        MIXED = "mixed", "Mixed"
        WEAK = "weak", "Unlikely to do well"
        UNKNOWN = "unknown", "Not enough data"

    score = models.FloatField(
        null=True,
        blank=True,
        help_text="Our score for this IPO, from -1 to 1. Set by the scoring step.",
    )
    verdict = models.CharField(max_length=10, choices=Verdict, blank=True)
    scored_at = models.DateTimeField(null=True, blank=True)
    score_inputs = models.JSONField(
        default=dict, blank=True, help_text="All the numbers that gave the score."
    )

    source_url = models.URLField(max_length=1000, blank=True)

    # Exchange codes. The source gives them after the listing. We use them to get the listing price.
    nse_symbol = models.CharField(max_length=30, blank=True)
    bse_code = models.CharField(max_length=10, blank=True)
    isin = models.CharField(max_length=12, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-open_date", "name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "open_date"], name="unique_ipo_name_open_date"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Set the time of the GMP and of the subscription when their values change."""
        old = (
            type(self)
            .objects.filter(pk=self.pk)
            .values("gmp", "gmp_updated_at", "subscription_times", "subscription_updated_at")
            .first()
            if self.pk
            else None
        )
        now = timezone.now()
        touched = []
        for value, stamp in (
            ("gmp", "gmp_updated_at"),
            ("subscription_times", "subscription_updated_at"),
        ):
            new_value = getattr(self, value)
            if new_value is None:
                continue
            if old is None:
                changed = getattr(self, stamp) is None
            else:
                # Do not replace a time that the caller set on purpose.
                changed = old[value] != new_value and getattr(self, stamp) == old[stamp]
            if changed:
                setattr(self, stamp, now)
                touched.append(stamp)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and touched:
            kwargs["update_fields"] = [*update_fields, *touched]
        super().save(*args, **kwargs)

    @property
    def gmp_pct(self) -> float | None:
        """The GMP in percent of the upper price band."""
        if self.gmp is None or not self.price_band_high:
            return None
        return float(self.gmp / self.price_band_high * 100)
