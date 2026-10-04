from django.contrib import admin

from .models import Ipo


@admin.register(Ipo)
class IpoAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "status", "open_date", "close_date", "gmp", "score")
    list_filter = ("status", "category")
    search_fields = ("name",)
    date_hierarchy = "open_date"
    autocomplete_fields = ("company",)
    readonly_fields = ("created_at", "updated_at")
