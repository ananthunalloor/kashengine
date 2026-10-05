from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.llm.client import LLMClient, LLMUnavailable
from apps.news.compare import ModelReport, evaluate_model, label_for, load_items


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


class Command(BaseCommand):
    help = (
        "Run the same labelled headlines on one or more LLM models and compare them. "
        "Example: compare_models llama3.2:3b llama3.1:8b. "
        "It does not change the database."
    )

    def add_arguments(self, parser):
        parser.add_argument("models", nargs="*", help="Model names. Default: LLM_MODEL.")
        parser.add_argument("--file", help="A CSV file with the columns label, title, summary.")
        parser.add_argument("--verbose", action="store_true", help="Show the score of each item.")

    def handle(self, *args, **options):
        names = options["models"] or [settings.LLM_MODEL]
        try:
            items = load_items(options["file"])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        reports: list[ModelReport] = []
        for name in names:
            self.stdout.write(f"Scoring {len(items)} items with {name} ...")
            with LLMClient(model=name) as llm:
                try:
                    reports.append(evaluate_model(llm, items))
                except LLMUnavailable as exc:
                    raise CommandError(str(exc)) from exc

        self.stdout.write("")
        self.stdout.write(
            f"{'Model':<24}{'Items':>6}{'Failed':>8}{'Accuracy':>10}{'Error':>8}{'Sec/item':>10}"
        )
        for report in reports:
            error = report.mean_abs_error
            self.stdout.write(
                f"{report.model:<24}{len(report.items):>6}{report.failures:>8}"
                f"{_percent(report.accuracy):>10}"
                f"{'-' if error is None else f'{error:.2f}':>8}"
                f"{report.seconds_per_item:>10.1f}"
            )
        for other in reports[1:]:
            self.stdout.write(
                f"Same class, {reports[0].model} and {other.model}: "
                f"{_percent(reports[0].agreement_with(other))}"
            )
        if len(reports) == 1:
            self.stdout.write("Tip: give two models to compare them.")

        if options["verbose"]:
            self.stdout.write("")
            for index, item in enumerate(items):
                scores = [r.scores[index] for r in reports]
                shown = "  ".join(
                    "  none" if s is None else f"{s:+.2f} {label_for(s)[:3]}" for s in scores
                )
                self.stdout.write(f"{item.label[:3]}  {shown}  {item.title[:70]}")
