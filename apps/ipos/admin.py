from django.contrib import admin

from .models import Ipo


@admin.register(Ipo)
class IpoAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "status",
        "open_date",
        "close_date",
        "gmp",
        "subscription_times",
        "score",
        "verdict",
        "listing_gain_pct",
    )
    list_filter = ("status", "category", "verdict")
    search_fields = ("name",)
    date_hierarchy = "open_date"
    autocomplete_fields = ("company",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "score",
        "verdict",
        "scored_at",
        "score_inputs",
        "gmp_updated_at",
        "subscription_updated_at",
    )
