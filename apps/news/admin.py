from django.contrib import admin

from .models import NewsArticle


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "published_at", "has_full_text", "sentiment_score")
    list_filter = ("source", "published_at")
    search_fields = ("title", "summary", "text", "url")
    date_hierarchy = "published_at"
    autocomplete_fields = ("companies",)
    readonly_fields = ("fetched_at", "text_scraped_at")

    @admin.display(boolean=True, description="Full text")
    def has_full_text(self, obj):
        return bool(obj.text)
