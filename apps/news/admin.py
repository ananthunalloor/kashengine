from django.contrib import admin

from .models import NewsArticle


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "published_at", "sentiment_score")
    list_filter = ("source", "published_at")
    search_fields = ("title", "text", "url")
    date_hierarchy = "published_at"
    readonly_fields = ("fetched_at",)
