"""Management command: add or update companies from a CSV file."""

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.companies.models import Company

STARTER_FILE = Path(__file__).resolve().parents[2] / "data" / "starter_companies.csv"


class Command(BaseCommand):
    """Import companies from a CSV file."""

    help = (
        "Add or update companies from a CSV file. "
        "Columns: symbol, name, sector, aliases (aliases are separated by |). "
        "Use --starter for the small built-in list of large companies."
    )

    def add_arguments(self, parser):
        """Add the file and --starter arguments."""
        parser.add_argument("file", nargs="?", help="Path of the CSV file.")
        parser.add_argument("--starter", action="store_true", help="Use the built-in starter list.")

    def handle(self, *args, **options):
        """Read the CSV file and save each row as a Company."""
        if options["starter"]:
            path = STARTER_FILE
        elif options["file"]:
            path = Path(options["file"])
        else:
            raise CommandError("Give a CSV file, or use --starter.")
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        created = updated = 0
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                symbol = (row.get("symbol") or "").strip().upper()
                name = (row.get("name") or "").strip()
                if not symbol or not name:
                    self.stdout.write(
                        self.style.WARNING(f"Skip a row with no symbol or name: {row}")
                    )
                    continue
                values = {"name": name}
                if sector := (row.get("sector") or "").strip():
                    values["sector"] = sector
                if aliases := [
                    a.strip() for a in (row.get("aliases") or "").split("|") if a.strip()
                ]:
                    values["aliases"] = aliases
                _, was_created = Company.objects.update_or_create(symbol=symbol, defaults=values)
                created += was_created
                updated += not was_created
        self.stdout.write(f"Companies: {created} added, {updated} updated.")
