from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol", "sector", "last_updated")
    list_filter = ("sector",)
    search_fields = ("name", "symbol")
    readonly_fields = ("created_at",)
