from django.core.management.base import BaseCommand

from apps.markets.evaluation import evaluate_pending
from apps.markets.quotes import fetch_quotes


class Command(BaseCommand):
    help = "Download the index and global cue prices now. Then check the old predictions."

    def handle(self, *args, **options):
        result = fetch_quotes()
        self.stdout.write(f"Quotes: {result['saved']} rows saved.")
        for symbol, error in result["failed"].items():
            self.stdout.write(self.style.WARNING(f"  Failed: {symbol}: {error}"))
        stats = evaluate_pending()
        self.stdout.write(
            "Predictions: {evaluated} checked, {void} void, {waiting} waiting.".format(**stats)
        )
