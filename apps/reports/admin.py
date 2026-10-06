from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("date", "prediction", "confidence", "created_at")
    list_filter = ("prediction",)
    date_hierarchy = "date"
    readonly_fields = ("created_at", "data")
