from django.contrib import admin

from .models import DeliveryLog


@admin.register(DeliveryLog)
class DeliveryLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "channel", "status", "recipient", "report")
    list_filter = ("channel", "status")
    search_fields = ("recipient", "error")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
