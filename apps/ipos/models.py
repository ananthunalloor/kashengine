"""Database model for IPOs.

The app has one model, `Ipo`. Several parts of the app write to it:

- `apps/ipos/collect.py` and the `collect_ipos`, `import_ipo_csv` and `update_ipo` commands
  save the list data and the manual entries.
- `apps/ipos/gmp.py` saves the GMP and the subscription.
- `apps/ipos/listing.py` saves the listing price.
- `apps/ipos/scoring.py` saves the score and the verdict.

The daily report (`apps/reports`) and the web pages (`apps/web`) only read the model.
"""

from typing import ClassVar

from django.db import models
from django.utils import timezone


class Ipo(models.Model):
    """An IPO (initial public offer), from announcement to listing.

    One row is one IPO. The pair (`name`, `open_date`) is unique. An IPO that changes its dates
    keeps its row, because `apps/ipos/collect.py` matches a record by the normalized company name.

    Key rules:

    - `status` follows the dates. `refresh_statuses` and `save_record` set it. It is not a user
      input.
    - `gmp_updated_at` and `subscription_updated_at` say how fresh the numbers are. The score
      ignores a number that is older than `IPO_METRIC_MAX_AGE_HOURS`. `Ipo.save` keeps these
      times in step with the values.
    - `listing_price` and `listing_gain_pct` are the result. They are empty before the listing.
    - `score`, `verdict`, `scored_at` and `score_inputs` belong to `apps/ipos/scoring.py`.
      The admin shows them as read only.
    - `company` is an optional link to `apps.companies.Company`. The link becomes empty if the
      company is deleted.
    """

    class Category(models.TextChoices):
        """The market segment of an IPO."""

        MAINBOARD = "mainboard", "Mainboard"
        SME = "sme", "SME"

    class Status(models.TextChoices):
        """The stage of an IPO. The dates decide it (see `compute_status`)."""

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
        """The outcome of the scoring rule. `UNKNOWN` means that there was not enough data."""

        GOOD = "good", "Likely to do well"
        MIXED = "mixed", "Mixed"
        WEAK = "weak", "Unlikely to do well"
        UNKNOWN = "unknown", "Not enough data"

    score = models.FloatField(
        null=True,
        blank=True,
        help_text="Our score for this IPO, from -1 to 1. Set by the scoring step.",
    )
    verdict = models.CharField(max_length=10, choices=Verdict.choices, blank=True)
    scored_at = models.DateTimeField(null=True, blank=True)
    score_inputs = models.JSONField(
        default=dict, blank=True, help_text="All the numbers that gave the score."
    )

    source_url = models.URLField(max_length=1000, blank=True)
    upstox_id = models.CharField(max_length=200, null=True, blank=True, unique=True)
    upstox_data = models.JSONField(default=dict, blank=True)
    upstox_updated_at = models.DateTimeField(null=True, blank=True)

    # Exchange codes. The source gives them after the listing. We use them to get the listing price.
    nse_symbol = models.CharField(max_length=30, blank=True)
    bse_code = models.CharField(max_length=10, blank=True)
    isin = models.CharField(max_length=12, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-open_date", "name"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["name", "open_date"], name="unique_ipo_name_open_date"),
        ]

    def __str__(self):
        """Return the name of the IPO."""
        return self.name

    def save(self, *args, **kwargs):
        """Save the IPO and set the time of the GMP and of the subscription when they change.

        The method compares the new `gmp` and `subscription_times` with the saved row. If a
        value is new or different, and the caller did not also change its time field, the time
        field becomes now. For a new row, the time becomes now when it is empty. A value of
        `None` never sets a time.

        If the caller sets the time field itself (for example to the time that a source
        gives), the method keeps that time.

        Args:
            args: Positional arguments for `Model.save`.
            kwargs: Keyword arguments for `Model.save`. If `update_fields` is given, the
                method adds the time fields that it changed to that list.

        Side effects:
            Runs one extra query to read the saved row when the object has a primary key.
            Writes the row.

        Note:
            The method compares the values in memory. It does this also when `update_fields`
            does not list the value field. `updated_at` is not added to `update_fields`.
        """
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
        """Return the GMP in percent of the upper price band.

        The value is `None` when there is no GMP, or when the upper price band is empty or zero.
        A negative GMP gives a negative percent.
        """
        if self.gmp is None or not self.price_band_high:
            return None
        return float(self.gmp / self.price_band_high * 100)
