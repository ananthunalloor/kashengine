from django.db import models


class Company(models.Model):
    """A listed company. Screener.in data is saved here and refreshed on a schedule."""

    name = models.CharField(max_length=200)
    symbol = models.CharField(max_length=50, unique=True, help_text="NSE or BSE symbol.")
    aliases = models.JSONField(
        default=list,
        blank=True,
        help_text='Other names used in news, for example ["SBI", "State Bank of India"].',
    )
    sector = models.CharField(max_length=100, blank=True)
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

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self):
        return f"{self.name} ({self.symbol})"
