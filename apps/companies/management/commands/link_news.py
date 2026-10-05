from django.core.management.base import BaseCommand

from apps.companies.matching import link_articles


class Command(BaseCommand):
    help = "Link news articles to the companies that they name."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all", action="store_true", help="Check all articles, not only recent ones."
        )
        parser.add_argument(
            "--hours", type=int, default=48, help="Check articles from the last N hours."
        )

    def handle(self, *args, **options):
        result = link_articles(since_hours=None if options["all"] else options["hours"])
        self.stdout.write(f"News: {result['checked']} articles checked, {result['linked']} linked.")
