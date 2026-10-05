from django.core.management.base import BaseCommand

from apps.llm.client import LLMClient
from apps.news.sentiment import score_pending


class Command(BaseCommand):
    help = "Score the sentiment of new articles now, with the local LLM."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, help="Maximum number of articles.")
        parser.add_argument("--model", help="Use this model, not LLM_MODEL.")

    def handle(self, *args, **options):
        with LLMClient(model=options["model"]) as llm:
            stats = score_pending(limit=options["limit"], llm=llm)
        self.stdout.write(f"Sentiment: {stats['scored']} scored, {stats['failed']} failed.")
        if stats["stopped"]:
            self.stdout.write(
                self.style.WARNING(
                    "Stopped: the LLM server is not available or has no model. "
                    "Run: python manage.py llm_check --pull"
                )
            )
