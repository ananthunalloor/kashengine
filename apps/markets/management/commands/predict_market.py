from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.markets.prediction import make_prediction


class Command(BaseCommand):
    help = (
        "Make the Nifty 50 prediction for the next trading day (today, if it is a trading day). "
        "Download the quotes first (fetch_quotes) and score the news (score_news)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--date", help="The day to predict, as YYYY-MM-DD.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Make it again. This works only until the result is known.",
        )

    def handle(self, *args, **options):
        target = None
        if options["date"]:
            try:
                target = date.fromisoformat(options["date"])
            except ValueError as exc:
                raise CommandError("Use the date format YYYY-MM-DD.") from exc

        prediction, created = make_prediction(target_day=target, force=options["force"])
        if not created:
            self.stdout.write(
                "A prediction for this day exists already, and it is not changed. "
                "Use --force to make it again (before the result is known)."
            )

        self.stdout.write(
            f"Prediction for {prediction.target_date}: {prediction.direction.upper()} "
            f"(confidence {prediction.confidence:.2f}, score {prediction.score:+.2f})"
        )
        news = "-" if prediction.news_score is None else f"{prediction.news_score:+.2f}"
        glob = "-" if prediction.global_score is None else f"{prediction.global_score:+.2f}"
        self.stdout.write(f"  News {news} ({prediction.news_articles} articles), global {glob}")
        for cue in prediction.inputs.get("cues", []):
            self.stdout.write(
                f"  {cue['name']:<12}{cue['change_pct']:>+7.2f}%  as of {cue['as_of']}"
            )
        for note in prediction.inputs.get("notes", []):
            self.stdout.write(self.style.WARNING(f"  Note: {note}"))
        self.stdout.write(
            "Confidence is not a probability. Check: python manage.py prediction_stats"
        )
