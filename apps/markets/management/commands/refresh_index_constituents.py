"""Refresh the saved official Nifty constituent lists."""

from django.core.management.base import BaseCommand, CommandError

from apps.markets.index_constituents import IndexConstituentError, refresh_index_constituents


class Command(BaseCommand):
    help = "Refresh Nifty 50/100/200/500 and Midcap/Smallcap index constituents."

    def handle(self, *args, **options):
        try:
            results = refresh_index_constituents()
        except IndexConstituentError as exc:
            raise CommandError(str(exc)) from exc
        total = sum(results.values())
        self.stdout.write(
            self.style.SUCCESS(f"Refreshed {len(results)} indexes with {total} constituents.")
        )
