"""Admin for the companies app."""

from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin list and search for Company."""

    list_display = ("name", "symbol", "sector", "last_updated")
    list_filter = ("sector",)
    search_fields = ("name", "symbol")
    readonly_fields = ("created_at",)
