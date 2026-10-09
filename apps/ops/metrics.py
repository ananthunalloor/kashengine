"""System and application metrics for the metrics page.

Host numbers come from /proc and the standard library, so there is no extra package. On a system
without /proc (macOS, Windows) the host numbers are left out.
"""

import contextlib
import os
import shutil
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import django
import redis
from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import connection
from django.db.models import Avg, Count, Max, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from kombu.exceptions import KombuError

from apps.companies.models import Company
from apps.delivery.models import DeliveryLog
from apps.ipos.models import Ipo
from apps.markets.models import IndexQuote, Prediction
from apps.news.models import NewsArticle
from apps.reports.models import Report

from .health import KB, read_meminfo
from .models import AuditEvent, LoginEvent, TaskRun

DEFAULT_DAYS = 14
REDIS_TIMEOUT_SECONDS = 2.0
STARTED_AT = time.time()  # When this process started.

TABLES = (
    ("News articles", NewsArticle),
    ("Companies", Company),
    ("IPOs", Ipo),
    ("Market quotes", IndexQuote),
    ("Predictions", Prediction),
    ("Reports", Report),
    ("Deliveries", DeliveryLog),
    ("Task runs", TaskRun),
    ("Login events", LoginEvent),
    ("Audit events", AuditEvent),
    ("Sessions", Session),
)


def task_stats(days: int = 7) -> list[dict]:
    """The runs of each job in the last `days` days: counts, success rate, and durations."""
    since = timezone.now() - timedelta(days=days)
    rows = (
        TaskRun.objects.filter(created_at__gte=since)
        .values("label")
        .annotate(
            runs=Count("id"),
            ok=Count("id", filter=Q(status=TaskRun.Status.SUCCESS)),
            failed=Count("id", filter=Q(status=TaskRun.Status.FAILURE)),
            avg_ms=Avg("duration_ms"),
            max_ms=Max("duration_ms"),
            last_started=Max("started_at"),
        )
        .order_by("label")
    )
    stats = []
    for row in rows:
        finished = row["ok"] + row["failed"]
        stats.append(
            {**row, "success_rate": round(row["ok"] / finished * 100) if finished else None}
        )
    return stats


def day_range(days: int = DEFAULT_DAYS) -> list[date]:
    """The last `days` days, oldest first, ending today (local time)."""
    today = timezone.localdate()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def daily_counts(queryset, field: str, days: int = DEFAULT_DAYS) -> list[int]:
    """How many rows have `field` on each of the last `days` days. Days without rows give 0."""
    since = timezone.now() - timedelta(days=days)
    rows = (
        queryset.filter(**{f"{field}__gte": since})
        .annotate(day=TruncDate(field))
        .values("day")
        .annotate(n=Count("id"))
    )
    per_day = {row["day"]: row["n"] for row in rows}
    return [per_day.get(day, 0) for day in day_range(days)]


def charts(days: int = DEFAULT_DAYS) -> list[dict]:
    """The series for the charts on the metrics page. Each has a title, labels, and values."""
    labels = [day.strftime("%d %b") for day in day_range(days)]
    runs = TaskRun.objects
    return [
        {
            "title": "Task runs",
            "labels": labels,
            "values": daily_counts(runs.filter(status=TaskRun.Status.SUCCESS), "created_at", days),
            "alerts": daily_counts(runs.filter(status=TaskRun.Status.FAILURE), "created_at", days),
            "note": "Done, and failed (red).",
        },
        {
            "title": "News articles fetched",
            "labels": labels,
            "values": daily_counts(NewsArticle.objects.all(), "fetched_at", days),
        },
        {
            "title": "News articles scored",
            "labels": labels,
            "values": daily_counts(NewsArticle.objects.all(), "scored_at", days),
        },
        {
            "title": "Telegram deliveries",
            "labels": labels,
            "values": daily_counts(
                DeliveryLog.objects.filter(status=DeliveryLog.Status.SENT), "created_at", days
            ),
            "alerts": daily_counts(
                DeliveryLog.objects.filter(status=DeliveryLog.Status.FAILED), "created_at", days
            ),
            "note": "Sent, and failed (red).",
        },
        {
            "title": "Logins",
            "labels": labels,
            "values": daily_counts(
                LoginEvent.objects.filter(kind=LoginEvent.Kind.LOGIN), "created_at", days
            ),
            "alerts": daily_counts(
                LoginEvent.objects.filter(kind=LoginEvent.Kind.FAILED), "created_at", days
            ),
            "note": "Logins, and failed logins (red).",
        },
    ]


def table_counts() -> list[tuple[str, int]]:
    """The number of rows in the main tables."""
    return [(name, model.objects.count()) for name, model in TABLES]


def database_size() -> int | None:
    """The size of the database in bytes, if we can tell."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database())")
            return cursor.fetchone()[0]
    if connection.vendor == "sqlite":
        name = connection.settings_dict.get("NAME")
        path = Path(str(name)) if name else None
        if path and path.is_file():
            return path.stat().st_size
    return None


def host_stats() -> dict:
    """Load, memory, disk, and the uptime of the host and of this process."""
    info = read_meminfo()
    usage = shutil.disk_usage(settings.BASE_DIR)
    stats: dict = {
        "cpu_count": os.cpu_count(),
        "memory_total": info.get("MemTotal"),
        "memory_available": info.get("MemAvailable"),
        "disk_total": usage.total,
        "disk_used": usage.used,
        "disk_free": usage.free,
        "python": sys.version.split()[0],
        "django": django.get_version(),
        "process_uptime_seconds": int(time.time() - STARTED_AT),
        "load": None,
        "host_uptime_seconds": None,
    }
    with contextlib.suppress(OSError, AttributeError):  # No load average on Windows.
        stats["load"] = tuple(round(value, 2) for value in os.getloadavg())
    with contextlib.suppress(OSError, ValueError, IndexError):  # No /proc on macOS or Windows.
        stats["host_uptime_seconds"] = int(float(Path("/proc/uptime").read_text().split()[0]))
    return stats


def redis_stats() -> dict | None:
    """Memory, clients, uptime, and the queue length of Redis. None if Redis is down."""
    try:
        client = redis.Redis.from_url(
            settings.CELERY_BROKER_URL,
            socket_timeout=REDIS_TIMEOUT_SECONDS,
            socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
        )
        info = client.info()
        return {
            "version": info.get("redis_version"),
            "memory": info.get("used_memory_human"),
            "clients": info.get("connected_clients"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "queue_length": client.llen("celery"),
        }
    except redis.RedisError:
        return None


def worker_stats() -> list[dict] | None:
    """The tasks that each worker runs and holds now. None if no worker or broker answers."""
    from config.celery import app  # noqa: PLC0415  # Keeps the import cost out of web start-up.

    inspector = app.control.inspect(timeout=1.0)
    try:
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}
    except (OSError, KombuError):  # The broker (Redis) is down. The page must still open.
        return None
    names = sorted(set(active) | set(reserved))
    if not names:
        return None
    return [
        {
            "name": name,
            "active": len(active.get(name, [])),
            "reserved": len(reserved.get(name, [])),
        }
        for name in names
    ]


def llm_stats() -> dict:
    """How the sentiment scoring is going."""
    since = timezone.now() - timedelta(hours=24)
    scored = NewsArticle.objects.filter(scored_at__gte=since)
    waiting = NewsArticle.objects.filter(
        scored_at__isnull=True, sentiment_attempts__lt=settings.SENTIMENT_MAX_ATTEMPTS
    )
    return {
        "model": settings.LLM_MODEL,
        "scored_24h": scored.count(),
        "waiting": waiting.count(),
        "gave_up": NewsArticle.objects.filter(
            scored_at__isnull=True, sentiment_attempts__gte=settings.SENTIMENT_MAX_ATTEMPTS
        ).count(),
    }


def format_bytes(value: int | None) -> str:
    """12.3 MB. An empty value gives a dash."""
    if value is None:
        return "–"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < KB or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= KB
    return "–"
