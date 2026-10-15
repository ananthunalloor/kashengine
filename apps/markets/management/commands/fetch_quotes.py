"""Management command: download the market quotes now.

Run it with `python manage.py fetch_quotes`. It does the same work as the Celery task
`markets.fetch_quotes`, but at once and with output on the terminal.
"""

from django.core.management.base import BaseCommand

from apps.markets.evaluation import evaluate_pending
from apps.markets.quotes import fetch_quotes


class Command(BaseCommand):
    """Download quotes and check the old predictions.

    The command calls `quotes.fetch_quotes` and then `evaluation.evaluate_pending`. It has no
    arguments.
    """

    help = "Download the index and global cue prices now. Then check the old predictions."

    def handle(self, *args, **options):
        """Download the quotes, check the predictions, and print the counts.

        The command prints the number of saved rows, one warning line for each symbol that
        failed, and the counts of checked, void and waiting predictions. A failed symbol does not
        change the exit code.

        Args:
            args: Not used.
            options: The parsed command options. The command has no own options.

        Side effects:
            Network calls to Yahoo Finance. Writes to the `IndexQuote` and `Prediction` tables.
        """
        result = fetch_quotes()
        self.stdout.write(f"Quotes: {result['saved']} rows saved.")
        for symbol, error in result["failed"].items():
            self.stdout.write(self.style.WARNING(f"  Failed: {symbol}: {error}"))
        stats = evaluate_pending()
        self.stdout.write(
            "Predictions: {evaluated} checked, {void} void, {waiting} waiting.".format(**stats)
        )
