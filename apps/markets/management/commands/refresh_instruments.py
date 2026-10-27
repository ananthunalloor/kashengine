"""Management command: refresh NSE and BSE instruments from Upstox's daily master."""

from django.core.management.base import BaseCommand, CommandError

from apps.markets.instrument_master import InstrumentMasterError, refresh_instruments


class Command(BaseCommand):
    """Refresh the NSE/BSE instrument catalog."""

    help = (
        "Download the current Upstox instrument master and refresh all NSE/BSE equity, "
        "index, futures and options records."
    )

    def handle(self, *args, **options):
        """Refresh the catalog and report the imported coverage."""
        try:
            stats = refresh_instruments()
        except InstrumentMasterError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            "NSE/BSE instruments: {instruments} active ({equities} equity listings), "
            "{instruments_added} added; {companies_created} companies added.".format(**stats)
        )
