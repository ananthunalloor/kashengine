"""Admin for the news app."""

from django.contrib import admin

from .models import NewsArticle


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    """Admin for news articles."""

    list_display = (
        "title",
        "source",
        "published_at",
        "has_full_text",
        "sentiment_score",
        "relevance",
    )
    list_filter = ("source", "published_at", "sentiment_model")
    search_fields = ("title", "summary", "text", "url")
    date_hierarchy = "published_at"
    autocomplete_fields = ("companies",)
    readonly_fields = ("fetched_at", "text_scraped_at", "scored_at")

    @admin.display(boolean=True, description="Full text")
    def has_full_text(self, obj):
        """Return True if the article has scraped full text."""
        return bool(obj.text)
