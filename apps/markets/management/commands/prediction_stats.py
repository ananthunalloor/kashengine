"""Management command: show the accuracy of the predictions."""

from django.core.management.base import BaseCommand

from apps.markets.evaluation import MIN_RESULTS_TO_TRUST, accuracy_stats


def _share(part: dict) -> str:
    """Format a {"n", "correct"} count as "correct/n (percent)"."""
    if not part["n"]:
        return "no results"
    return f"{part['correct']}/{part['n']} ({part['correct'] / part['n'] * 100:.0f}%)"


class Command(BaseCommand):
    """Show the accuracy of the predictions."""

    help = "Show how good the predictions were, and compare them with a simple baseline."

    def handle(self, *args, **options):
        """Print the accuracy numbers and the baseline."""
        stats = accuracy_stats()
        self.stdout.write(
            f"Results: {stats['total']}   Waiting: {stats['pending']}   Void: {stats['void']}"
        )
        if not stats["total"]:
            self.stdout.write("No results yet. A result comes after the market closes.")
            return

        overall = {"n": stats["total"], "correct": stats["correct"]}
        self.stdout.write(f"Accuracy:          {_share(overall)}")
        baseline = stats["baseline_accuracy"] * 100
        self.stdout.write(
            f"Baseline:          {baseline:.0f}% "
            f"(always guess '{stats['baseline_direction']}', the most common result)"
        )
        self.stdout.write(f"Last {stats['recent']['n']} results:  {_share(stats['recent'])}")
        self.stdout.write(f"Confidence >= 0.6: {_share(stats['high_confidence'])}")
        for direction, part in stats["by_prediction"].items():
            self.stdout.write(f"  Predicted {direction:<5}   {_share(part)}")
        actual = "  ".join(f"{d} {n}" for d, n in stats["actual_counts"].items())
        self.stdout.write(f"Real results:      {actual}")

        if not stats["enough_results"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Only {stats['total']} results. Wait for at least {MIN_RESULTS_TO_TRUST} "
                    "before you trust these numbers."
                )
            )
        elif stats["accuracy"] <= stats["baseline_accuracy"]:
            self.stdout.write(self.style.WARNING("The predictions do not beat the baseline yet."))
