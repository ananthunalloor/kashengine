"""The jobs that an admin can start by hand.

Only the jobs in this list can run. An admin cannot type a command or an argument. A job is
either a Celery task or a management command with fixed arguments. Commands run in a Celery
worker (the task `ops.run_command`), so the web server does not wait for them and they use the
network access of the worker.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.http import HttpRequest
from django.utils import timezone

from config.celery import app as celery_app

from . import audit
from .models import TaskRun

logger = logging.getLogger(__name__)

TASK = "task"
COMMAND = "command"
RUN_COMMAND_TASK = "ops.run_command"
BUSY_WINDOW = timedelta(minutes=30)  # A run that is not done after this time does not block.
MESSAGE_EXPIRES_SECONDS = 3600  # A job that no worker takes in this time is dropped.


class JobBusyError(Exception):
    """The same job is already waiting or running."""


class JobDispatchError(Exception):
    """The job could not be sent to the queue (the broker is down, for example)."""


@dataclass(frozen=True)
class Job:
    """One job on the Jobs page."""

    key: str
    label: str
    description: str
    kind: str  # TASK or COMMAND
    target: str  # The Celery task name, or the command name.
    args: tuple[str, ...] = ()  # Fixed arguments of a command.
    group: str = "Other"
    confirm: str = ""  # If set, the admin must confirm. The text says what the job does.

    @property
    def run_label(self) -> str:
        """The name that the run history uses for this job."""
        if self.kind == TASK:
            return self.target
        return " ".join(["command:", self.target, *self.args])

    @property
    def task_name(self) -> str:
        """The Celery task that runs this job."""
        return self.target if self.kind == TASK else RUN_COMMAND_TASK


JOBS: tuple[Job, ...] = (
    Job(
        "news-fetch",
        "Fetch news feeds",
        "Read the RSS feeds. New articles start the company links, the scrape, and the scoring.",
        TASK,
        "news.fetch_feeds",
        group="News",
    ),
    Job(
        "news-scrape",
        "Scrape article text",
        "Download the full text of articles that have none. Then start the scoring.",
        TASK,
        "news.scrape_articles",
        group="News",
    ),
    Job(
        "news-score",
        "Score news sentiment",
        "Score the new articles with the local LLM. It can take a long time.",
        TASK,
        "news.score_articles",
        group="News",
    ),
    Job(
        "companies-link",
        "Link news to companies",
        "Link recent articles to the companies that they name.",
        TASK,
        "companies.link_news",
        group="Companies",
    ),
    Job(
        "companies-refresh",
        "Refresh company data",
        "Read old company data from Screener.in. It does nothing if SCREENER_ENABLED is false.",
        TASK,
        "companies.refresh_stale",
        group="Companies",
    ),
    Job(
        "markets-quotes",
        "Fetch market quotes",
        "Download the index and global cue prices. Then check the old predictions.",
        TASK,
        "markets.fetch_quotes",
        group="Markets",
    ),
    Job(
        "markets-predict",
        "Make the prediction",
        "Predict the next trading day from the news and the global cues.",
        TASK,
        "markets.predict",
        group="Markets",
    ),
    Job(
        "ipos-collect",
        "Collect IPOs",
        "Read the IPO list, then update the status and the scores.",
        TASK,
        "ipos.collect",
        group="IPOs",
    ),
    Job(
        "ipos-metrics",
        "Refresh IPO numbers",
        "Update the GMP, the subscription, and the listing prices. Then score again.",
        TASK,
        "ipos.refresh_metrics",
        group="IPOs",
    ),
    Job(
        "ipos-score",
        "Score IPOs",
        "Score the IPOs again with the data that we have.",
        TASK,
        "ipos.score",
        group="IPOs",
    ),
    Job(
        "report-send",
        "Build and send the daily report",
        "Build today's report and send it to the Telegram chats that did not get it yet.",
        TASK,
        "delivery.send_daily_report",
        group="Report",
        confirm="This sends the report to the Telegram chats now.",
    ),
    Job(
        "ops-prune",
        "Clean old history",
        "Delete old task runs, login events, and sessions. Mark lost runs as failed.",
        TASK,
        "ops.prune",
        group="System",
    ),
    Job(
        "llm-check",
        "Check the LLM server",
        "Check that the LLM server is up and has the model.",
        COMMAND,
        "llm_check",
        group="Checks",
    ),
    Job(
        "telegram-check",
        "Check the Telegram bot",
        "Check the bot token and show the chats that wrote to the bot.",
        COMMAND,
        "telegram_check",
        group="Checks",
    ),
    Job(
        "prediction-stats",
        "Prediction accuracy",
        "Show how good the predictions were, compared with a simple baseline.",
        COMMAND,
        "prediction_stats",
        group="Checks",
    ),
    Job(
        "ipo-stats",
        "IPO verdict accuracy",
        "Show how good the IPO verdicts were, compared with a simple baseline.",
        COMMAND,
        "ipo_stats",
        group="Checks",
    ),
    Job(
        "ipo-refresh-force",
        "Refresh IPO data (forced)",
        "Run the GMP and listing steps even if their settings are off. Shows the details.",
        COMMAND,
        "refresh_ipo_data",
        ("--force",),
        group="Forced runs",
    ),
    Job(
        "ipo-collect-force",
        "Collect IPOs (forced)",
        "Read the IPO list even if IPO_FETCH_ENABLED is false.",
        COMMAND,
        "collect_ipos",
        ("--force",),
        group="Forced runs",
    ),
    Job(
        "predict-force",
        "Make the prediction again",
        "Make today's prediction again. This works only until the result is known.",
        COMMAND,
        "predict_market",
        ("--force",),
        group="Forced runs",
        confirm="This replaces the saved prediction for the next trading day.",
    ),
    Job(
        "report-build-force",
        "Build the report again",
        "Build the report again, also if it exists. It does not send it.",
        COMMAND,
        "build_report",
        ("--force",),
        group="Forced runs",
        confirm="This replaces the saved report text for today.",
    ),
    Job(
        "telegram-test",
        "Send a Telegram test message",
        "Send a short test message to the chats in TELEGRAM_CHAT_IDS.",
        COMMAND,
        "send_report",
        ("--test",),
        group="Forced runs",
        confirm="This sends a test message to the Telegram chats now.",
    ),
)

JOBS_BY_KEY: dict[str, Job] = {job.key: job for job in JOBS}
COMMAND_ALLOWLIST: frozenset[tuple[str, tuple[str, ...]]] = frozenset(
    (job.target, job.args) for job in JOBS if job.kind == COMMAND
)


def dispatch(task_name: str, args: list, task_id: str) -> None:
    """Send a task to the queue. Tests replace this function."""
    celery_app.send_task(task_name, args=args, task_id=task_id, expires=MESSAGE_EXPIRES_SECONDS)


def active_run(job: Job) -> TaskRun | None:
    """The newest run of the job that waits or runs, if it is recent."""
    since = timezone.now() - BUSY_WINDOW
    return (
        TaskRun.objects.filter(
            label=job.run_label,
            status__in=[TaskRun.Status.PENDING, TaskRun.Status.STARTED],
            created_at__gte=since,
        )
        .order_by("-created_at")
        .first()
    )


def start_job(job: Job, user, request: HttpRequest | None = None) -> TaskRun:
    """Queue a job for a user and return its run row.

    Raises:
        JobBusyError: The same job waits or runs now.
        JobDispatchError: The queue did not take the job.
    """
    if active_run(job) is not None:
        msg = f"{job.label} is already waiting or running."
        raise JobBusyError(msg)

    task_id = str(uuid.uuid4())
    args = [job.target, list(job.args)] if job.kind == COMMAND else []
    run = TaskRun.objects.create(
        task_id=task_id,
        task_name=job.task_name,
        label=job.run_label,
        trigger=TaskRun.Trigger.MANUAL,
        triggered_by=user,
        args=" ".join(job.args),
    )
    audit.record(user, "run job", job.run_label, request=request)
    try:
        dispatch(job.task_name, args, task_id)
    except Exception as exc:
        logger.exception("Could not queue job %s.", job.key)
        run.status = TaskRun.Status.FAILURE
        run.error = f"The job could not be queued: {exc}"
        run.finished_at = timezone.now()
        run.save()
        msg = "The job could not be queued. Is Redis running?"
        raise JobDispatchError(msg) from exc
    return run
