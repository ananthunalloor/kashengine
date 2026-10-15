"""Management command that checks the LLM server and its model."""

from django.core.management.base import BaseCommand, CommandError

from apps.llm.client import LLMClient, LLMError


class Command(BaseCommand):
    """Check that the LLM server is up and has the model.

    Run it with `python manage.py llm_check`. It exits with an error (`CommandError`) when the
    server is not available, or when the model is missing and `--pull` is not given.
    """

    help = "Check that the LLM server is up and has the model. Use --pull to download the model."

    def add_arguments(self, parser):
        """Add the --model and --pull options.

        Args:
            parser: The argument parser of the command. The method adds `--model` (a model name
                to check instead of `LLM_MODEL`) and `--pull` (download the model if it is
                missing).
        """
        parser.add_argument("--model", help="Check this model, not LLM_MODEL.")
        parser.add_argument(
            "--pull", action="store_true", help="Download the model if it is missing."
        )

    def handle(self, *args, **options):
        """Run the check, and pull the model when asked.

        The command prints the server address and the model name. If the model is on the server,
        it prints OK and stops. If the model is missing and `--pull` is set, it downloads the
        model. This can take many minutes.

        Args:
            args: Positional arguments from Django. The command does not use them.
            options: The parsed options. The command reads `model` and `pull`.

        Raises:
            CommandError: The model is missing and `--pull` is not set, or the LLM client
                raises an `LLMError`.

        Side effects:
            Sends HTTP requests to the LLM server. With `--pull`, the server downloads the model.
        """
        with LLMClient(model=options["model"]) as llm:
            self.stdout.write(f"Server: {llm.base_url}")
            self.stdout.write(f"Model:  {llm.model}")
            try:
                if llm.has_model():
                    self.stdout.write(self.style.SUCCESS("OK: the model is ready."))
                    return
                if not options["pull"]:
                    raise CommandError(
                        f"The model is not on the server. Run this command with --pull "
                        f"(or: ollama pull {llm.model})."
                    )
                self.stdout.write("Downloading the model. This can take many minutes...")
                llm.pull_model()
                self.stdout.write(self.style.SUCCESS("Done. The model is ready."))
            except LLMError as exc:
                raise CommandError(str(exc)) from exc
