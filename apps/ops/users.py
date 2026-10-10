"""Queries and actions for the user monitoring pages."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from axes.models import AccessAttempt
from axes.utils import reset as axes_reset
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db.models import Count, IntegerField, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.siteconfig import axes_hooks, conf

from .models import LoginEvent

FAILED_WINDOW_HOURS = 24
SUSPICIOUS_FAILED_LOGINS = 5  # Failed logins from one address in the window.


class UserActionError(Exception):
    """An admin action is not allowed. The message says why."""


@dataclass(frozen=True)
class SessionInfo:
    """A login session that has not expired."""

    key: str
    user_id: int
    expires: datetime
    ip_address: str | None
    user_agent: str
    started: datetime | None


def users_with_stats(search: str = "") -> QuerySet:
    """All users with their login counts and the failed logins of the last 24 hours."""
    user_model = get_user_model()
    since = timezone.now() - timedelta(hours=FAILED_WINDOW_HOURS)
    failed = (
        LoginEvent.objects.filter(
            kind=LoginEvent.Kind.FAILED, username=OuterRef("username"), created_at__gte=since
        )
        .order_by()
        .values("username")
        .annotate(n=Count("id"))
        .values("n")
    )
    users = user_model.objects.annotate(
        login_count=Count("login_events", filter=Q(login_events__kind=LoginEvent.Kind.LOGIN)),
        failed_24h=Coalesce(Subquery(failed, output_field=IntegerField()), 0),
    )
    if search.strip():
        term = search.strip()[:100]
        users = users.filter(Q(username__icontains=term) | Q(email__icontains=term))
    return users.order_by("-is_superuser", "-is_staff", "username")


def active_sessions() -> list[SessionInfo]:
    """All sessions that have not expired, with the address of the login that made them."""
    now = timezone.now()
    found = []
    for session in Session.objects.filter(expire_date__gt=now).order_by("-expire_date"):
        try:
            data = session.get_decoded()
            user_id = int(data.get("_auth_user_id", ""))
        except (ValueError, TypeError):
            continue  # No user (an anonymous session), or data that we cannot read.
        login = (
            LoginEvent.objects.filter(session_key=session.session_key, kind=LoginEvent.Kind.LOGIN)
            .order_by("-created_at")
            .first()
        )
        found.append(
            SessionInfo(
                key=session.session_key,
                user_id=user_id,
                expires=session.expire_date,
                ip_address=login.ip_address if login else None,
                user_agent=login.user_agent if login else "",
                started=login.created_at if login else None,
            )
        )
    return found


def sessions_of(user_id: int) -> list[SessionInfo]:
    """The active sessions of one user."""
    return [s for s in active_sessions() if s.user_id == user_id]


def end_session(key: str, *, current_key: str = "") -> int:
    """End one session. The session of the admin who clicks cannot be ended here."""
    if key and key == current_key:
        msg = "This is your own session. Use Log out to end it."
        raise UserActionError(msg)
    return Session.objects.filter(session_key=key).delete()[0]


def end_user_sessions(user_id: int, *, current_key: str = "") -> int:
    """End all sessions of a user, except the session of the admin who clicks."""
    keys = [s.key for s in sessions_of(user_id) if s.key != current_key]
    return Session.objects.filter(session_key__in=keys).delete()[0]


def set_user_active(user, active: bool, *, acting_user) -> None:
    """Turn a user on or off. Turning a user off also ends the sessions of the user."""
    if not active:
        if user.pk == acting_user.pk:
            msg = "You cannot turn off your own account."
            raise UserActionError(msg)
        others = (
            get_user_model()
            .objects.filter(is_superuser=True, is_active=True)
            .exclude(pk=user.pk)
            .exists()
        )
        if user.is_superuser and not others:
            msg = "This is the last active superuser. Turn it off only after you make another."
            raise UserActionError(msg)
    user.is_active = active
    user.save(update_fields=["is_active"])
    if not active:
        end_user_sessions(user.pk)


def login_events(kind: str = "", search: str = "", hours: int | None = None) -> QuerySet:
    """Login events, newest first, with optional filters."""
    events = LoginEvent.objects.select_related("user")
    if kind in LoginEvent.Kind.values:
        events = events.filter(kind=kind)
    if search.strip():
        term = search.strip()[:100]
        events = events.filter(Q(username__icontains=term) | Q(ip_address__startswith=term))
    if hours:
        events = events.filter(created_at__gte=timezone.now() - timedelta(hours=hours))
    return events


def failed_logins_by_address(hours: int = FAILED_WINDOW_HOURS, limit: int = 10) -> list[dict]:
    """The addresses with the most failed logins in the last `hours` hours."""
    since = timezone.now() - timedelta(hours=hours)
    rows = (
        LoginEvent.objects.filter(kind=LoginEvent.Kind.FAILED, created_at__gte=since)
        .values("ip_address")
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )
    return [{**row, "suspicious": row["count"] >= SUSPICIOUS_FAILED_LOGINS} for row in rows]


def lockouts() -> list[dict]:
    """The addresses that are locked out now (django-axes), with the failed tries of each.

    An address is locked when its failed logins reach the limit, and the lockout time is not over.
    """
    limit = conf.LOGIN_FAILURE_LIMIT
    wait = axes_hooks.cooloff(None)
    now = timezone.now()
    by_address: dict[str, dict] = {}
    for attempt in AccessAttempt.objects.order_by("attempt_time"):
        row = by_address.setdefault(
            attempt.ip_address or "unknown",
            {"ip_address": attempt.ip_address, "failures": 0, "usernames": set(), "last": None},
        )
        row["failures"] += attempt.failures_since_start
        row["usernames"].add(attempt.username or "")
        row["last"] = attempt.attempt_time
    locked = []
    for row in by_address.values():
        if row["failures"] < limit:
            continue
        until = row["last"] + wait if wait else None
        if until is not None and until <= now:
            continue
        locked.append({**row, "usernames": sorted(row["usernames"]), "until": until})
    return sorted(locked, key=lambda r: r["last"], reverse=True)


def unlock(ip_address: str) -> int:
    """Remove the failed tries of an address, so it can try again. Return how many."""
    return axes_reset(ip=ip_address)
