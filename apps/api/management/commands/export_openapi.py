"""Write the OpenAPI document of an API version to a file or to standard output.

The committed file `docs/openapi/v1.json` comes from this command. A test fails when the file
is older than the code. The Docusaurus build reads the file to make the API reference pages.
"""

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.api.app.api import api as api_app
from apps.api.v1.api import api as api_v1

APIS = {"v1": api_v1, "app": api_app}


def render(version: str = "v1") -> str:
    """Return the OpenAPI document of one API version as stable JSON text.

    The keys keep the order of the schema. The text ends with a new line and uses an indent
    of two spaces, so a Git diff shows only real changes.

    Args:
        version: The major version, for example `v1`.

    Returns:
        The JSON text.

    Raises:
        KeyError: If the version does not exist.
    """
    schema = APIS[version].get_openapi_schema()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


class Command(BaseCommand):
    """Export the OpenAPI document (`manage.py export_openapi`)."""

    help = "Write the OpenAPI document of an API version."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add the options `--api-version` and `--output`.

        Args:
            parser: The parser of the command.
        """
        parser.add_argument("--api-version", "--api", default="v1", choices=sorted(APIS))
        parser.add_argument("--output", help="File to write. The default is standard output.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Write the document.

        Args:
            args: Not used.
            options: The parsed options.

        Raises:
            CommandError: If the output file cannot be written.
        """
        text = render(options["api_version"])
        target = options["output"]
        if not target:
            self.stdout.write(text, ending="")
            return
        path = Path(target)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            raise CommandError(f"Cannot write {path}: {exc}") from exc
        self.stdout.write(f"Wrote {path}")
