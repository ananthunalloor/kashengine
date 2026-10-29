from django.db import migrations, models


FEEDS = [
    (
        "The Hindu BusinessLine",
        "Business",
        "https://www.thehindubusinessline.com/feeder/default.rss",
        "india",
        "South India",
    ),
    (
        "CNBC",
        "World News",
        "https://www.cnbc.com/id/100727362/device/rss/rss.html",
        "international",
        "North America",
    ),
    (
        "BBC News",
        "Business",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "international",
        "Europe",
    ),
    (
        "South China Morning Post",
        "Business",
        "https://www.scmp.com/rss/92/feed",
        "international",
        "East Asia",
    ),
]


def seed_regional_feeds(apps, schema_editor):
    NewsFeed = apps.get_model("news", "NewsFeed")
    NewsArticle = apps.get_model("news", "NewsArticle")

    regions = {
        "Business Standard": "West India",
        "Economic Times": "West India",
        "Mint": "North India",
        "Moneycontrol": "West India",
    }
    for source, region in regions.items():
        NewsFeed.objects.filter(source=source).update(coverage="india", region=region)
        NewsArticle.objects.filter(source=source).update(coverage="india", region=region)

    for source, name, url, coverage, region in FEEDS:
        NewsFeed.objects.get_or_create(
            url=url,
            defaults={
                "source": source,
                "name": name,
                "coverage": coverage,
                "region": region,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("news", "0005_store")]

    operations = [
        migrations.AddField(
            model_name="newsarticle",
            name="coverage",
            field=models.CharField(
                choices=[("india", "India"), ("international", "International")],
                default="india",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="newsarticle",
            name="region",
            field=models.CharField(default="India", max_length=50),
        ),
        migrations.AddField(
            model_name="newsfeed",
            name="coverage",
            field=models.CharField(
                choices=[("india", "India"), ("international", "International")],
                default="india",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="newsfeed",
            name="region",
            field=models.CharField(default="India", max_length=50),
        ),
        migrations.RunPython(seed_regional_feeds, migrations.RunPython.noop),
    ]