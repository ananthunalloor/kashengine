"""Admin for the markets app."""

from django.contrib import admin

from .models import IndexQuote, Prediction


@admin.register(IndexQuote)
class IndexQuoteAdmin(admin.ModelAdmin):
    """Admin list for IndexQuote."""

    list_display = ("symbol", "day", "close", "change_pct", "updated_at")
    list_filter = ("symbol",)
    date_hierarchy = "day"
    readonly_fields = ("updated_at",)


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    """Admin list for Prediction."""

    list_display = (
        "target_date",
        "direction",
        "confidence",
        "score",
        "actual_direction",
        "actual_change_pct",
        "correct",
    )
    list_filter = ("direction", "correct")
    date_hierarchy = "target_date"
    readonly_fields = ("created_at", "evaluated_at")
