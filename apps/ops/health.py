"""Health checks for the system. Each check returns a status and a short text.

The checks only read. A check that raises an error counts as a failed check, so one broken part
cannot hide the others. The result is kept for a few seconds, because the overview page refreshes
itself.
"""

import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Max
from django.utils import timezone

from apps.delivery.models import DeliveryLog
from apps.delivery.service import configured_chat_ids
from apps.llm.client import LLMClient, LLMError
from apps.markets.models import IndexQuote, Prediction
from apps.markets.trading import is_trading_day, market_tz, previous_trading_day, today_ist
from apps.news.models import NewsArticle
from apps.reports.models import Report
from apps.siteconfig import conf

from . import schedule
from .models import TaskRun

logger = logging.getLogger(__name__)

OK, WARN, FAIL, SKIP = "ok", "warn", "fail", "skip"
SEVERITY = {SKIP: 0, OK: 1, WARN: 2, FAIL: 3}

CACHE_KEY = "ops.health"
CACHE_SECONDS = 10
CHECK_TIMEOUT_SECONDS = 2.0

DISK_WARN_PCT = 80
DISK_FAIL_PCT = 92
MEMORY_WARN_AVAILABLE_PCT = 10
MEMORY_FAIL_AVAILABLE_PCT = 5
TASK_FAILURES_WARN = 1
TASK_FAILURES_FAIL = 5
NEWS_FAIL_AFTER_HOURS = 24
SCORING_BACKLOG_AGE_HOURS = 6
QUOTES_FAIL_AFTER_DAYS = 5
QUOTES_EVENING_HOUR = 18  # IST. The evening run gets the final quotes at 17:30.
HOURS_IN_TWO_DAYS = 48
PREDICTION_GRACE_MINUTES = (
    30  # A prediction can be late. We warn this long after the last run time.
)
REPORT_GRACE_MINUTES = 10
KB = 1024
MIB = 1024 * 1024


@dataclass(frozen=True)
class Check:
    """The result of one check."""

    key: str
    name: str
    status: str
    summary: str
    detail: str = ""
    latency_ms: int | None = None


def worst(statuses) -> str:
    """The most serious status of a group. An empty group is "skip"."""
    return max(statuses, key=SEVERITY.__getitem__, default=SKIP)


def _ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def check_database() -> Check:
    """Run a trivial query and time it."""
    start = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    latency = _ms(start)
    return Check("database", "Database", OK, f"{connection.vendor}, {latency} ms", "", latency)


def check_migrations() -> Check:
    """Check that all migrations are applied."""
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if plan:
        names = ", ".join(f"{m.app_label}.{m.name}" for m, _backwards in plan[:5])
        return Check("migrations", "Migrations", WARN, f"{len(plan)} not applied", names)
    return Check("migrations", "Migrations", OK, "All applied")


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_timeout=CHECK_TIMEOUT_SECONDS,
        socket_connect_timeout=CHECK_TIMEOUT_SECONDS,
    )


def check_redis() -> Check:
    """Ping Redis (the Celery broker) and read its memory use."""
    client = _redis_client()
    start = time.perf_counter()
    client.ping()
    latency = _ms(start)
    info = client.info()
    memory, clients = info.get("used_memory_human", "?"), info.get("connected_clients", "?")
    detail = f"{memory} used, {clients} clients"
    return Check("redis", "Redis", OK, f"Answers in {latency} ms", detail, latency)


def check_workers() -> Check:
    """Ask the Celery workers to answer a ping."""
    from config.celery import app  # noqa: PLC0415  # Keeps the import cost out of web start-up.

    answers = app.control.inspect(timeout=1.0).ping() or {}
    if not answers:
        detail = "Jobs and schedules do not run."
        return Check("workers", "Celery workers", FAIL, "No worker answered", detail)
    return Check(
        "workers", "Celery workers", OK, f"{len(answers)} answered", ", ".join(sorted(answers))
    )


def check_beat() -> Check:
    """Check that the scheduled tasks ran when they were due.

    The check uses the automatic runs in the task history. Without a history, it cannot judge.
    """
    now = timezone.now()
    late = []
    judged = 0
    for task_name in sorted({entry.task for entry in schedule.entries()}):
        last = (
            TaskRun.objects.filter(
                task_name=task_name,
                trigger=TaskRun.Trigger.AUTO,
                started_at__isnull=False,
            )
            .order_by("-started_at")
            .first()
        )
        if last is None or last.started_at is None:
            continue
        judged += 1
        delay = schedule.overdue_by(task_name, last.started_at, now)
        if delay is not None:
            late.append(f"{task_name} ({int(delay.total_seconds() // 60)} min late)")
    if not judged:
        return Check("beat", "Scheduler (beat)", SKIP, "No scheduled run in the history yet")
    if late:
        return Check(
            "beat",
            "Scheduler (beat)",
            WARN,
            f"{len(late)} task(s) are late",
            ", ".join(late),
        )
    return Check("beat", "Scheduler (beat)", OK, f"{judged} scheduled tasks on time")


def check_llm() -> Check:
    """Ask the LLM server for its models."""
    start = time.perf_counter()
    try:
        with LLMClient(timeout=3.0) as client:
            models = client.list_models()
            has_model = client.has_model()
    except LLMError as exc:
        return Check("llm", "LLM server (Ollama)", FAIL, "Cannot reach the server", str(exc))
    latency = _ms(start)
    if not has_model:
        return Check(
            "llm",
            "LLM server (Ollama)",
            WARN,
            f"Model {conf.LLM_MODEL} is missing",
            f"On the server: {', '.join(models) or 'no models'}",
            latency,
        )
    return Check("llm", "LLM server (Ollama)", OK, f"{conf.LLM_MODEL} is ready", "", latency)


def check_telegram() -> Check:
    """Check the Telegram settings and the last delivery. It makes no request to Telegram."""
    if not conf.TELEGRAM_BOT_TOKEN or not configured_chat_ids():
        return Check("telegram", "Telegram", WARN, "Not set up", "Set the token and the chat IDs.")
    last = DeliveryLog.objects.order_by("-created_at").first()
    if last is None:
        return Check("telegram", "Telegram", OK, "Set up. Nothing sent yet")
    if last.status == DeliveryLog.Status.FAILED:
        return Check(
            "telegram", "Telegram", WARN, "The last delivery failed", last.error[:300] or ""
        )
    return Check("telegram", "Telegram", OK, f"Last delivery: {last.created_at:%Y-%m-%d %H:%M}")


def check_disk() -> Check:
    """Check the free space of the disk of the app."""
    usage = shutil.disk_usage(settings.BASE_DIR)
    used_pct = usage.used / usage.total * 100
    free_gb = usage.free / KB**3
    summary = f"{used_pct:.0f}% used, {free_gb:.1f} GB free"
    if used_pct >= DISK_FAIL_PCT:
        return Check("disk", "Disk", FAIL, summary)
    if used_pct >= DISK_WARN_PCT:
        return Check("disk", "Disk", WARN, summary)
    return Check("disk", "Disk", OK, summary)


def read_meminfo() -> dict[str, int]:
    """Read /proc/meminfo as bytes. An empty dict on a system without it."""
    try:
        with open("/proc/meminfo", encoding="ascii") as handle:  # noqa: PTH123  # A /proc file.
            lines = handle.read().splitlines()
    except OSError:
        return {}
    values = {}
    for line in lines:
        name, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[name] = int(parts[0]) * KB
    return values


def check_memory() -> Check:
    """Check the available memory of the host."""
    info = read_meminfo()
    total, available = info.get("MemTotal"), info.get("MemAvailable")
    if not total or available is None:
        return Check("memory", "Memory", SKIP, "Not available on this system")
    available_pct = available / total * 100
    summary = f"{available / MIB / KB:.1f} GB free of {total / MIB / KB:.1f} GB"
    if available_pct < MEMORY_FAIL_AVAILABLE_PCT:
        return Check("memory", "Memory", FAIL, summary)
    if available_pct < MEMORY_WARN_AVAILABLE_PCT:
        return Check("memory", "Memory", WARN, summary)
    return Check("memory", "Memory", OK, summary)


def check_task_failures() -> Check:
    """Count the failed runs of the last 24 hours."""
    since = timezone.now() - timedelta(hours=24)
    failed = TaskRun.objects.filter(status=TaskRun.Status.FAILURE, created_at__gte=since)
    count = failed.count()
    if not count:
        return Check("failures", "Task failures (24 h)", OK, "None")
    names = ", ".join(sorted(set(failed.values_list("label", flat=True)))[:5])
    status = FAIL if count >= TASK_FAILURES_FAIL else WARN
    return Check("failures", "Task failures (24 h)", status, f"{count} failed", names)


def _age_text(delta: timedelta) -> str:
    hours = delta.total_seconds() / 3600
    return f"{hours:.0f} h ago" if hours < HOURS_IN_TWO_DAYS else f"{hours / 24:.0f} days ago"


def check_news_fresh() -> Check:
    """Check that new articles arrive."""
    latest = NewsArticle.objects.aggregate(latest=Max("fetched_at"))["latest"]
    if latest is None:
        return Check("news", "News", SKIP, "No articles yet")
    age = timezone.now() - latest
    summary = f"Newest article fetched {_age_text(age)}"
    limit = timedelta(hours=conf.NEWS_STALE_AFTER_HOURS)
    if age > timedelta(hours=NEWS_FAIL_AFTER_HOURS):
        return Check("news", "News", FAIL, summary)
    if age > limit:
        return Check("news", "News", WARN, summary)
    return Check("news", "News", OK, summary)


def check_scoring_backlog() -> Check:
    """Count the old articles that are still not scored."""
    cutoff = timezone.now() - timedelta(hours=SCORING_BACKLOG_AGE_HOURS)
    backlog = NewsArticle.objects.filter(
        scored_at__isnull=True,
        sentiment_attempts__lt=conf.SENTIMENT_MAX_ATTEMPTS,
        fetched_at__lt=cutoff,
    ).count()
    summary = f"{backlog} articles wait for a score"
    if backlog > conf.SENTIMENT_BATCH_SIZE:
        return Check("scoring", "Scoring backlog", WARN, summary, "Is the LLM server up?")
    return Check("scoring", "Scoring backlog", OK, summary)


def check_quotes_fresh() -> Check:
    """Check that the quotes include the last trading day."""
    latest = IndexQuote.objects.aggregate(latest=Max("day"))["latest"]
    if latest is None:
        return Check("quotes", "Market quotes", SKIP, "No quotes yet")
    today = today_ist()
    summary = f"Newest quote: {latest}"
    if (today - latest) > timedelta(days=QUOTES_FAIL_AFTER_DAYS):
        return Check("quotes", "Market quotes", FAIL, summary)
    evening = timezone.now().astimezone(market_tz()).hour >= QUOTES_EVENING_HOUR
    expected = today if is_trading_day(today) and evening else previous_trading_day(today)
    if latest < expected:
        return Check("quotes", "Market quotes", WARN, summary, f"Expected {expected}.")
    return Check("quotes", "Market quotes", OK, summary)


def _late(task_name: str, grace_minutes: int) -> bool | None:
    """True if the task should have run today and its grace time is over.

    None means that the task is not scheduled today. The times come from the schedule in the
    database, so a change on the dashboard moves the check.
    """
    now = timezone.now().astimezone(market_tz())
    times = schedule.times_on(task_name, now.date())
    if not times:
        return None
    hour, minute = times[-1]  # The last run of the day: a retry counts.
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now >= due + timedelta(minutes=grace_minutes)


def check_prediction() -> Check:
    """Check that today's prediction exists, on a trading day after its scheduled time."""
    today = today_ist()
    exists = Prediction.objects.filter(target_date=today).exists()
    if not is_trading_day(today):
        return Check("prediction", "Prediction", OK, "Market closed today")
    if exists:
        return Check("prediction", "Prediction", OK, f"Made for {today}")
    late = _late("markets.predict", PREDICTION_GRACE_MINUTES)
    if late is None:
        return Check("prediction", "Prediction", SKIP, "Not scheduled today")
    if late:
        return Check("prediction", "Prediction", WARN, f"Missing for {today}")
    return Check("prediction", "Prediction", OK, "Not due yet")


def check_report() -> Check:
    """Check that today's report exists, on a trading day after its scheduled time."""
    today = today_ist()
    exists = Report.objects.filter(date=today).exists()
    if not is_trading_day(today):
        return Check("report", "Daily report", OK, "Market closed today")
    if exists:
        return Check("report", "Daily report", OK, f"Built for {today}")
    late = _late("delivery.send_daily_report", REPORT_GRACE_MINUTES)
    if late is None:
        return Check("report", "Daily report", SKIP, "Not scheduled today")
    if late:
        return Check("report", "Daily report", WARN, f"Missing for {today}")
    return Check("report", "Daily report", OK, "Not due yet")


@dataclass(frozen=True)
class CheckSpec:
    """A check function with the key and the name to show if the check itself fails."""

    key: str
    name: str
    run: Callable[[], Check]


# (group, checks). The overview page shows the groups in this order.
GROUPS: tuple[tuple[str, tuple[CheckSpec, ...]], ...] = (
    (
        "Services",
        (
            CheckSpec("database", "Database", check_database),
            CheckSpec("redis", "Redis", check_redis),
            CheckSpec("workers", "Celery workers", check_workers),
            CheckSpec("beat", "Scheduler (beat)", check_beat),
            CheckSpec("llm", "LLM server (Ollama)", check_llm),
            CheckSpec("telegram", "Telegram", check_telegram),
        ),
    ),
    (
        "Host",
        (
            CheckSpec("disk", "Disk", check_disk),
            CheckSpec("memory", "Memory", check_memory),
            CheckSpec("migrations", "Migrations", check_migrations),
        ),
    ),
    (
        "Data",
        (
            CheckSpec("news", "News", check_news_fresh),
            CheckSpec("scoring", "Scoring backlog", check_scoring_backlog),
            CheckSpec("quotes", "Market quotes", check_quotes_fresh),
            CheckSpec("prediction", "Prediction", check_prediction),
            CheckSpec("report", "Daily report", check_report),
            CheckSpec("failures", "Task failures (24 h)", check_task_failures),
        ),
    ),
)


def run_check(spec: CheckSpec) -> Check:
    """Run one check. An error in the check is a failed check, not a crash."""
    try:
        return spec.run()
    except Exception as exc:
        logger.warning("Health check %s failed: %s", spec.key, exc)
        detail = f"{type(exc).__name__}: {exc}"[:300]
        return Check(spec.key, spec.name, FAIL, "The check failed", detail)


def run_all(*, use_cache: bool = True) -> list[tuple[str, list[Check]]]:
    """Run all checks. Return [(group name, [check, ...]), ...]."""
    if use_cache:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached
    results = [(name, [run_check(spec) for spec in specs]) for name, specs in GROUPS]
    cache.set(CACHE_KEY, results, CACHE_SECONDS)
    return results


def overall(results: list[tuple[str, list[Check]]]) -> str:
    """The worst status of all checks."""
    return worst(check.status for _group, checks in results for check in checks)
