"""Health checks for the system. Each check returns a status and a short text.

The checks only read. A check that raises an error counts as a failed check, so one broken part
cannot hide the others. The result is kept for a few seconds, because the overview page refreshes
itself.

Each check is a function with no arguments that returns a `Check`. The `GROUPS` table lists the
checks in three groups: Services, Host, and Data. `run_all` runs every check through `run_check`
and keeps the result in the Django cache for `CACHE_SECONDS`. `overall` finds the worst status.

The overview view (`views.py`) calls `run_all` and `overall`. The template filters in
`templatetags/ops_extras.py` use the four status names. `metrics.py` imports `KB` and
`read_meminfo` from this module. The checks read the schedule through `schedule.py`, the task
history from `TaskRun`, and the settings through `apps.siteconfig.conf`. The dates of the market
checks use the IST market calendar of `apps.markets.trading`.

The four status names are `OK`, `WARN`, `FAIL`, and `SKIP`. `SEVERITY` ranks them. `SKIP` means
that the check has no data to judge.
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
    """The result of one check.

    The object is frozen. `run_all` keeps a list of these objects in the cache.

    Attributes:
        key: A short stable ID of the check, for example `database`.
        name: The name that the page shows.
        status: One of `OK`, `WARN`, `FAIL`, or `SKIP`.
        summary: One short line for the page.
        detail: Extra text. It is empty when there is nothing to add.
        latency_ms: The time of the check in milliseconds. `None` when the check does not time
            itself.
    """

    key: str
    name: str
    status: str
    summary: str
    detail: str = ""
    latency_ms: int | None = None


def worst(statuses) -> str:
    """Return the most serious status of a group of statuses.

    The order is `skip`, `ok`, `warn`, `fail`, from the least to the most serious (`SEVERITY`).

    Args:
        statuses: An iterable of status names. Each name must be a key of `SEVERITY`.

    Returns:
        The most serious status name. `skip` when the group is empty.
    """
    return max(statuses, key=SEVERITY.__getitem__, default=SKIP)


def _ms(start: float) -> int:
    """Return the milliseconds since `start`, rounded to a whole number.

    Args:
        start: A value that `time.perf_counter()` gave earlier.

    Returns:
        The elapsed time in milliseconds.
    """
    return round((time.perf_counter() - start) * 1000)


def check_database() -> Check:
    """Run a trivial query and time it.

    The check runs `SELECT 1` on the default database connection. It does not catch errors. When
    the database is down, the error goes to `run_check`.

    Returns:
        A `Check` with the status `ok`. The summary has the database vendor and the time in
        milliseconds.
    """
    start = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    latency = _ms(start)
    return Check("database", "Database", OK, f"{connection.vendor}, {latency} ms", "", latency)


def check_migrations() -> Check:
    """Check that all migrations are applied.

    The check asks the migration executor for the plan to reach the latest migrations. An empty
    plan means that nothing is missing.

    Returns:
        A `Check` with the status `ok` when all migrations are applied. Otherwise the status is
        `warn`. The summary has the number of missing migrations. The detail lists the first five.
    """
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if plan:
        names = ", ".join(f"{m.app_label}.{m.name}" for m, _backwards in plan[:5])
        return Check("migrations", "Migrations", WARN, f"{len(plan)} not applied", names)
    return Check("migrations", "Migrations", OK, "All applied")


def _redis_client() -> redis.Redis:
    """Return a Redis client for the Celery broker.

    The client uses `CELERY_BROKER_URL`. The connect time and the read time are both
    `CHECK_TIMEOUT_SECONDS`.

    Returns:
        A new `redis.Redis` client. It connects when the first command runs.
    """
    return redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_timeout=CHECK_TIMEOUT_SECONDS,
        socket_connect_timeout=CHECK_TIMEOUT_SECONDS,
    )


def check_redis() -> Check:
    """Ping Redis (the Celery broker) and read its memory use.

    The check does not catch Redis errors. When Redis is down, the error goes to `run_check`.

    Returns:
        A `Check` with the status `ok`. The summary has the ping time. The detail has the memory
        use and the number of clients.
    """
    client = _redis_client()
    start = time.perf_counter()
    client.ping()
    latency = _ms(start)
    info = client.info()
    memory, clients = info.get("used_memory_human", "?"), info.get("connected_clients", "?")
    detail = f"{memory} used, {clients} clients"
    return Check("redis", "Redis", OK, f"Answers in {latency} ms", detail, latency)


def check_workers() -> Check:
    """Ask the Celery workers to answer a ping.

    The check waits up to one second for the answers.

    Returns:
        A `Check` with the status `ok` and the names of the workers that answered. The status is
        `fail` when no worker answers.

    Note:
        When Redis is down, the ping can raise an error. `run_check` turns it into a failed check.
    """
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

    For each task name of the enabled schedule entries, the check finds the newest run with the
    trigger `auto` and a start time. A task with no such run is not judged. For the other tasks,
    `schedule.overdue_by` finds how late the task is. A task is late when the next due time after
    its last run is more than `schedule.OVERDUE_GRACE` (10 minutes) in the past.

    Returns:
        A `Check` with the status `skip` when no task was judged. The status is `warn` when at
        least one task is late. The detail lists each late task with its delay in minutes. The
        status is `ok` otherwise.

    Note:
        A task that never ran is not reported as late. Only the history can show a late task.
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
    """Ask the LLM server for its models.

    The check opens a client with a timeout of 3 seconds. It lists the models and checks for the
    model of `conf.LLM_MODEL`.

    Returns:
        A `Check` with the status `fail` when the server does not answer. The detail has the error
        text. The status is `warn` when the server answers but the model is missing. The detail
        lists the models on the server. The status is `ok` when the model is there.
    """
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
    """Check the Telegram settings and the last delivery. It makes no request to Telegram.

    The check reads `conf.TELEGRAM_BOT_TOKEN`, the chat IDs, and the newest `DeliveryLog` row.

    Returns:
        A `Check`. The status is `warn` when the token or the chat IDs are not set. The status is
        `warn` when the newest delivery failed. The detail then has the first 300 characters of
        the error. The status is `ok` in all other cases, with or without a delivery.

    Security:
        The check never shows the token.
    """
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
    """Check the free space of the disk of the app.

    The check measures the disk that holds `settings.BASE_DIR`. It uses the share of used space.

    Returns:
        A `Check`. The status is `fail` at `DISK_FAIL_PCT` (92 percent) used or more. The status
        is `warn` at `DISK_WARN_PCT` (80 percent) or more. Otherwise it is `ok`. The summary has
        the used share and the free space in GB.
    """
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
    """Read the file `/proc/meminfo` and give the values in bytes.

    The file gives each value in kB. The function multiplies it by 1024. The function skips a
    line whose first value after the colon is not a number.

    Returns:
        A dict from the field name (for example `MemTotal` or `MemAvailable`) to bytes. The dict
        is empty when the file cannot be read, for example on macOS or Windows.
    """
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
    """Check the available memory of the host.

    The check uses the field `MemAvailable` of `/proc/meminfo` (see `read_meminfo`).

    Returns:
        A `Check`. The status is `skip` when the system has no `MemTotal` or `MemAvailable`. The
        status is `fail` when the available share is below `MEMORY_FAIL_AVAILABLE_PCT` (5
        percent). The status is `warn` below `MEMORY_WARN_AVAILABLE_PCT` (10 percent). Otherwise
        it is `ok`. The summary shows the sizes in GB (1024 to the power of 3 bytes).
    """
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
    """Count the failed runs of the last 24 hours.

    The check counts `TaskRun` rows with the status `failure` and a `created_at` time in the last
    24 hours.

    Returns:
        A `Check`. The status is `ok` with the summary `None` when there is no failed run. The
        status is `fail` at `TASK_FAILURES_FAIL` (5) failed runs or more. Otherwise it is `warn`.
        The detail lists up to five job labels, in alphabetical order.
    """
    since = timezone.now() - timedelta(hours=24)
    failed = TaskRun.objects.filter(status=TaskRun.Status.FAILURE, created_at__gte=since)
    count = failed.count()
    if not count:
        return Check("failures", "Task failures (24 h)", OK, "None")
    names = ", ".join(sorted(set(failed.values_list("label", flat=True)))[:5])
    status = FAIL if count >= TASK_FAILURES_FAIL else WARN
    return Check("failures", "Task failures (24 h)", status, f"{count} failed", names)


def _age_text(delta: timedelta) -> str:
    """Return a short text for an age, for example `5 h ago` or `3 days ago`.

    Args:
        delta: The age. It must not be negative.

    Returns:
        The age in whole hours when it is less than 48 hours. Otherwise the age in whole days.
    """
    hours = delta.total_seconds() / 3600
    return f"{hours:.0f} h ago" if hours < HOURS_IN_TWO_DAYS else f"{hours / 24:.0f} days ago"


def check_news_fresh() -> Check:
    """Check that new articles arrive.

    The check uses the newest `fetched_at` time of the `NewsArticle` rows.

    Returns:
        A `Check`. The status is `skip` when there is no article. The status is `fail` when the
        newest article is older than `NEWS_FAIL_AFTER_HOURS` (24 hours). The status is `warn` when
        it is older than `conf.NEWS_STALE_AFTER_HOURS`. Otherwise it is `ok`.

    Note:
        When `conf.NEWS_STALE_AFTER_HOURS` is more than 24, the `warn` state does not happen.
    """
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
    """Count the old articles that are still not scored.

    An article counts when it has no `scored_at` time, it has fewer scoring attempts than
    `conf.SENTIMENT_MAX_ATTEMPTS`, and it came more than `SCORING_BACKLOG_AGE_HOURS` (6 hours)
    ago. New articles do not count, because the scoring task is still to run for them.

    Returns:
        A `Check`. The status is `warn` when the count is more than `conf.SENTIMENT_BATCH_SIZE`.
        Otherwise it is `ok`. The summary has the count.
    """
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
    """Check that the quotes include the last trading day.

    The check uses the newest `day` of the `IndexQuote` rows. The expected day is today when
    today is a trading day and the IST time is `QUOTES_EVENING_HOUR` (18) or later. At other
    times the expected day is the previous trading day. The evening run of the quote task gets the
    final quotes at 17:30 IST.

    Returns:
        A `Check`. The status is `skip` when there are no quotes. The status is `fail` when the
        newest quote is more than `QUOTES_FAIL_AFTER_DAYS` (5) days old. The status is `warn` when
        it is older than the expected day. Otherwise it is `ok`.
    """
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
    """Tell if a task should have run today and its grace time is over.

    The times come from the schedule in the database, so a change on the dashboard moves the
    check. The function uses the last scheduled time of today, so a retry run counts. It compares
    the time with the clock of the market time zone (IST).

    Args:
        task_name: The Celery task name, for example `markets.predict`.
        grace_minutes: The minutes to wait after the last scheduled time before the task is late.

    Returns:
        `True` if the grace time is over. `False` if it is not over. `None` if the task has no
        enabled entry that runs today.
    """
    now = timezone.now().astimezone(market_tz())
    times = schedule.times_on(task_name, now.date())
    if not times:
        return None
    hour, minute = times[-1]  # The last run of the day: a retry counts.
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now >= due + timedelta(minutes=grace_minutes)


def check_prediction() -> Check:
    """Check that today's prediction exists, on a trading day after its scheduled time.

    The check looks for a `Prediction` with `target_date` equal to today (IST). The scheduled
    time of the task `markets.predict` plus `PREDICTION_GRACE_MINUTES` (30) sets when it is late.

    Returns:
        A `Check`. The status is `ok` when today is not a trading day, when the prediction exists,
        or when it is not yet due. The status is `skip` when the task has no run today. The status
        is `warn` when the prediction is missing and late.
    """
    today = today_ist()
    exists = Prediction.objects.filter(target_date=today).exists()
    if not is_trading_day(today):
        return Check("prediction", "Prediction", OK, "Market closed today")
    blocked = Prediction.objects.filter(target_date=today, direction="withheld").first()
    if blocked:
        reasons = blocked.inputs.get("learning", {}).get("watchdog", {}).get("reasons", [])
        return Check(
            "prediction", "Prediction", WARN, "Withheld by the watchdog", "; ".join(reasons)
        )
    if exists:
        return Check("prediction", "Prediction", OK, f"Made for {today}")
    late = _late("markets.predict", PREDICTION_GRACE_MINUTES)
    if late is None:
        return Check("prediction", "Prediction", SKIP, "Not scheduled today")
    if late:
        return Check("prediction", "Prediction", WARN, f"Missing for {today}")
    return Check("prediction", "Prediction", OK, "Not due yet")


def check_report() -> Check:
    """Check that today's report exists, on a trading day after its scheduled time.

    The check looks for a `Report` with `date` equal to today (IST). The scheduled time of the
    task `delivery.send_daily_report` plus `REPORT_GRACE_MINUTES` (10) sets when it is late.

    Returns:
        A `Check`. The status is `ok` when today is not a trading day, when the report exists, or
        when it is not yet due. The status is `skip` when the task has no run today. The status is
        `warn` when the report is missing and late.
    """
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
    """A check function with the key and the name to show if the check itself fails.

    `run_check` uses `key` and `name` to build a failed `Check` when `run` raises an error.

    Attributes:
        key: The ID of the check. It matches the `key` of the `Check` that `run` returns.
        name: The name that the page shows.
        run: A function with no arguments that returns a `Check`.
    """

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
    """Run one check. An error in the check is a failed check, not a crash.

    Args:
        spec: The check to run.

    Returns:
        The `Check` of the function. If the function raises any `Exception`, the result is a
        `Check` with the status `fail` and the summary `The check failed`. The detail has the
        error type and message, cut to 300 characters.

    Side effects:
        Writes one warning to the log when the check fails.
    """
    try:
        return spec.run()
    except Exception as exc:
        logger.warning("Health check %s failed: %s", spec.key, exc)
        detail = f"{type(exc).__name__}: {exc}"[:300]
        return Check(spec.key, spec.name, FAIL, "The check failed", detail)


def run_all(*, use_cache: bool = True) -> list[tuple[str, list[Check]]]:
    """Run all checks of `GROUPS`.

    The function keeps the result in the Django cache under `CACHE_KEY` for `CACHE_SECONDS` (10
    seconds). The overview page refreshes itself, and the cache stops a flood of real checks.

    Args:
        use_cache: When `True` (the default), the function returns the cached result if there is
            one. When `False`, it runs all checks again. In both cases it saves a new result in
            the cache after a real run.

    Returns:
        A list of pairs. Each pair has the group name and the list of `Check` objects of the group.
        The order is the order of `GROUPS`.

    Side effects:
        Runs every check. This makes network calls to Redis, Celery, and the LLM server. Writes
        the result to the cache.
    """
    if use_cache:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached
    results = [(name, [run_check(spec) for spec in specs]) for name, specs in GROUPS]
    cache.set(CACHE_KEY, results, CACHE_SECONDS)
    return results


def overall(results: list[tuple[str, list[Check]]]) -> str:
    """Return the worst status of all checks.

    Args:
        results: The value that `run_all` returns.

    Returns:
        The most serious status name (see `worst`). `skip` when there are no checks.
    """
    return worst(check.status for _group, checks in results for check in checks)
