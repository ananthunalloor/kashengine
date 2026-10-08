"""Management command that reads the RSS feeds and scrapes new articles."""

from django.core.management.base import BaseCommand

from apps.news.rss import fetch_all_feeds
from apps.news.scraper import scrape_pending


class Command(BaseCommand):
    """Read the RSS feeds and scrape new articles."""

    help = "Read the RSS feeds and scrape new articles now. For manual runs in dev."

    def add_arguments(self, parser):
        """Add the --no-scrape and --limit options."""
        parser.add_argument("--no-scrape", action="store_true", help="Read feeds only.")
        parser.add_argument("--limit", type=int, help="Maximum number of articles to scrape.")

    def handle(self, *args, **options):
        """Fetch the feeds, then scrape the full text unless --no-scrape is set."""
        result = fetch_all_feeds()
        self.stdout.write(f"Feeds: {result['new']} new articles.")
        for label, error in result["failed"].items():
            self.stdout.write(self.style.WARNING(f"  Failed: {label}: {error}"))

        if options["no_scrape"]:
            return
        stats = scrape_pending(limit=options["limit"])
        if stats.get("disabled"):
            self.stdout.write("Scrape is off (NEWS_SCRAPE_FULL_TEXT=false).")
            return
        self.stdout.write(
            "Scrape: {scraped} ok, {blocked} blocked by robots.txt, "
            "{failed} failed, {retry} to retry.".format(**stats)
        )
