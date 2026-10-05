from django.core.management.base import BaseCommand, CommandError

from apps.llm.client import LLMClient, LLMError


class Command(BaseCommand):
    help = "Check that the LLM server is up and has the model. Use --pull to download the model."

    def add_arguments(self, parser):
        parser.add_argument("--model", help="Check this model, not LLM_MODEL.")
        parser.add_argument(
            "--pull", action="store_true", help="Download the model if it is missing."
        )

    def handle(self, *args, **options):
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
