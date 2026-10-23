"""Django admin for the markets app.

The module registers `IndexQuote`, `Prediction`, and calendar exceptions. `Instrument` has no
admin class here. Admins edit the instruments on the Ops pages (Ops > Instruments).
"""

from django.contrib import admin

from .models import IndexQuote, Prediction, TradingCalendarDay


@admin.register(TradingCalendarDay)
class TradingCalendarDayAdmin(admin.ModelAdmin):
    """Manage exchange-announced holidays and special sessions with reasons."""

    list_display = ("day", "kind", "reason", "opens_at", "closes_at")
    list_filter = ("kind",)
    search_fields = ("reason",)
    date_hierarchy = "day"


@admin.register(IndexQuote)
class IndexQuoteAdmin(admin.ModelAdmin):
    """Admin list for `IndexQuote`.

    The list shows the symbol, the day, the close, the change and the save time. It has a filter
    for the symbol and a date drill-down. `updated_at` is read-only.
    """

    list_display = ("symbol", "day", "close", "change_pct", "updated_at")
    list_filter = ("symbol",)
    date_hierarchy = "day"
    readonly_fields = ("updated_at",)


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    """Admin list for `Prediction`.

    The list shows the prediction and the real result side by side. It has filters for the
    direction and for `correct`, and a date drill-down. `created_at` and `evaluated_at` are
    read-only.
    """

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
