"""Typed Ops presentation over shared Django contexts and existing action handlers."""

from datetime import date, datetime, time
from decimal import Decimal
from http import HTTPStatus
from typing import Any

from django import forms
from django.contrib.messages import ERROR, get_messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest
from django.template.response import TemplateResponse
from django.urls import Resolver404, resolve
from django.utils.crypto import salted_hmac
from ninja import Router

from apps.api.errors import ApiError
from apps.api.v1.common import ERRORS_WITH_VALIDATION
from apps.ops import users
from apps.ops.permissions import superuser_required
from apps.ops.templatetags.ops_extras import duration
from apps.siteconfig import conf

from .auth import OpsSession
from .schemas import (
    NavigationItem,
    OpsActionResult,
    OpsCell,
    OpsChartPoint,
    OpsChoice,
    OpsColumn,
    OpsField,
    OpsForm,
    OpsMessage,
    OpsPage,
    OpsRow,
    OpsSection,
    OpsTable,
)

router = Router(tags=["Ops workspace"], auth=OpsSession())

PAGES = {
    "overview",
    "jobs",
    "logs",
    "metrics",
    "users",
    "invites",
    "user",
    "subscriptions",
    "logins",
    "config",
    "settings",
    "settings_group",
    "schedule",
    "schedule_add",
    "schedule_edit",
    "feeds",
    "instruments",
    "backups",
}
ACTIONS = {
    "job_run",
    "invite_generate",
    "invite_revoke",
    "user_end_sessions",
    "user_revoke_tokens",
    "user_set_active",
    "user_access",
    "user_subscription_give",
    "user_subscription_end",
    "lockout_unlock",
    "settings_group",
    "schedule_add",
    "schedule_edit",
    "schedule_toggle",
    "schedule_delete",
    "schedule_reset",
    "feeds",
    "feed_toggle",
    "feed_delete",
    "instruments",
    "instrument_save",
    "instrument_delete",
    "backup_settings",
    "backup_run",
    "backup_export",
    "backup_import",
}


def cell(value: object, *, href: str = "", tone: str = "neutral") -> OpsCell:
    """Normalize an explicitly selected display value, never a whole model.

    Args:
        value: The selected display value.
        href: An optional application-local link.
        tone: The explicit semantic display color.

    Returns:
        A cell with text and a sortable value.
    """
    if isinstance(value, datetime):
        return OpsCell(text=value.isoformat(), kind="time", value=value.isoformat(), href=href)
    text = "" if value is None else str(value)
    return OpsCell(
        text=text,
        href=href,
        tone=tone,  # ty: ignore[invalid-argument-type]
        value=None
        if value is None
        else float(value)
        if isinstance(value, (int, float, Decimal))
        else text,
    )


def state(value: str) -> OpsCell:
    """Keep operational state semantics independent of market direction.

    Args:
        value: The recorded operational state.

    Returns:
        A cell with the corresponding status color.
    """
    tone = (
        "positive"
        if value.lower() in {"ok", "success", "active", "on", "login"}
        else "negative"
        if value.lower() in {"fail", "failure", "failed", "error", "critical", "expired"}
        else "warning"
        if value.lower() in {"warn", "warning", "pending", "started", "trial"}
        else "neutral"
    )
    return cell(value, tone=tone)


def row(**values) -> OpsRow:
    """Build only the named display columns.

    Args:
        **values: Explicitly selected column names and display values.

    Returns:
        A row containing normalized cells.
    """
    return OpsRow(
        cells={
            key: value if isinstance(value, OpsCell) else cell(value)
            for key, value in values.items()
        }
    )


def link(label: str, path: str) -> NavigationItem:
    """Use workspace-local links, retaining legacy pages separately.

    Args:
        label: The visible navigation label.
        path: The relative Ops page path.

    Returns:
        A React workspace navigation item.
    """
    return NavigationItem(label=label, url=f"/ops/{path}")


def action(
    path: str, label: str, *, fields=None, confirmation="", disabled=False, download=False
) -> OpsForm:
    """Describe a fixed action routed through the private session/CSRF boundary.

    Args:
        path: The allowlisted relative Ops action path.
        label: The submit button label.
        fields: Explicit input descriptors.
        confirmation: An optional destructive-action confirmation prompt.
        disabled: Whether the current user may submit the action.
        download: Whether the response is a file attachment.

    Returns:
        A form targeting the private action dispatcher.
    """
    return OpsForm(
        id=path,
        action=f"/api/app/ops/actions/{path}",
        label=label,
        fields=fields or [],
        confirmation=confirmation,
        disabled=disabled,
        download=download,
    )


def field(
    name: str, value: str, *, kind: str = "hidden", label: str = "", required=False
) -> OpsField:
    """Describe an action's small explicit payload.

    Args:
        name: The original Django input name.
        value: The initial serialized value.
        kind: The supported input widget kind.
        label: The visible input label.
        required: Whether the input must be supplied.

    Returns:
        An input descriptor for a workspace form.
    """
    return OpsField(name=name, label=label or name, value=value, kind=kind, required=required)  # ty: ignore[invalid-argument-type]


def form_data(form, path: str, label: str, *, help_by_name=None) -> OpsForm:
    """Serialize form widgets and errors without ever echoing password inputs.

    Args:
        form: The original bound or unbound Django form.
        path: The allowlisted relative action path.
        label: The submit button label.
        help_by_name: Optional help text overrides keyed by unprefixed field name.

    Returns:
        A form descriptor preserving field prefixes, choices, and validation errors.
    """
    result = action(path, label)
    result.errors = [str(error) for error in form.non_field_errors()] if form.is_bound else []
    for bound in form:
        widget = bound.field.widget
        kind = (
            "textarea"
            if isinstance(widget, forms.Textarea)
            else "select"
            if isinstance(widget, forms.Select)
            else getattr(widget, "input_type", "text")
        )
        if kind not in {
            "text",
            "password",
            "number",
            "checkbox",
            "select",
            "textarea",
            "date",
            "time",
            "file",
            "hidden",
        }:
            kind = "text"
        value = bound.value()
        if isinstance(value, (date, datetime, time)):
            value = value.isoformat()
        descriptor = OpsField(
            name=bound.html_name,
            label=str(bound.label),
            kind=kind,
            value="on"
            if kind == "checkbox"
            else ""
            if kind == "password" or value is None
            else str(value),
            checked=bool(value) if kind == "checkbox" else False,
            required=bound.field.required,
            help=str(bound.help_text),
            errors=[str(error) for error in bound.errors] if form.is_bound else [],
            max_length=getattr(bound.field, "max_length", None),
            min=str(bound.field.min_value)
            if getattr(bound.field, "min_value", None) is not None
            else None,
            max=str(bound.field.max_value)
            if getattr(bound.field, "max_value", None) is not None
            else None,
            step=str(widget.attrs["step"]) if "step" in widget.attrs else None,
        )
        if kind == "select":
            descriptor.choices = [
                OpsChoice(label=str(label), value=str(value))
                for value, label in bound.field.choices
            ]
        if help_by_name and bound.name in help_by_name:
            descriptor.help = help_by_name[bound.name]
        result.fields.append(descriptor)
    return result


def table(request: HttpRequest, rows: list[OpsRow], *, full=False, filters=()) -> OpsTable:
    """Search and sort the complete list before bounding the response to 1–100 rows.

    Args:
        request: The request containing search, filter, sort, and pagination state.
        rows: All explicitly selected display rows.
        full: Whether to process the full list on the server.
        filters: Column names offering exact-match filters.

    Returns:
        A server-paginated table or an explicitly bounded local table.

    Raises:
        ApiError: If page or page size is not an integer.
    """
    columns = list(dict.fromkeys(key for item in rows for key in item.cells))
    total = len(rows)
    choices = {
        key: sorted({item.cells[key].text for item in rows if key in item.cells}) for key in filters
    }
    if full:
        query = request.GET.get("q", "").strip().lower()[:200]
        if query:
            rows = [
                item
                for item in rows
                if any(query in value.text.lower() for value in item.cells.values())
            ]
        for key in filters:
            if chosen := request.GET.get(key, ""):
                rows = [item for item in rows if item.cells.get(key, cell("")).text == chosen]
        sort = request.GET.get("sort", "")
        key = sort.removeprefix("-")
        if key in columns:
            present = [item for item in rows if item.cells.get(key, cell(None)).value is not None]
            missing = [item for item in rows if item.cells.get(key, cell(None)).value is None]
            rows = (
                sorted(
                    present,
                    key=lambda item: sortable_value(item.cells[key]),
                    reverse=sort.startswith("-"),
                )
                + missing
            )
        try:
            size = min(100, max(1, int(request.GET.get("page_size") or conf.OPS_PAGE_SIZE)))
            number = max(1, int(request.GET.get("page") or 1))
        except ValueError as exc:
            raise ApiError("validation_error", "Page and page size must be integers.") from exc
        page = Paginator(rows, size).get_page(number)
        return OpsTable(
            columns=[OpsColumn(label=key.replace("_", " ").title(), key=key) for key in columns],
            rows=list(page.object_list),
            server=True,
            page=page.number,
            pages=page.paginator.num_pages,
            total=page.paginator.count,
            page_size=size,
            filters=list(filters),
            filter_choices=choices,
        )
    return OpsTable(
        columns=[OpsColumn(label=key.replace("_", " ").title(), key=key) for key in columns],
        rows=rows,
        total=total,
        filters=list(filters),
    )


def sortable_value(value: OpsCell) -> str | float:
    """Return a cell's sortable value; callers partition missing values separately.

    Args:
        value: The display cell to sort.

    Returns:
        Its numeric or text value, or an empty string for a missing value.
    """
    return value.value if value.value is not None else ""


def run_row(run) -> OpsRow:
    """Use run summaries, not stored task arguments, output, or results.

    Args:
        run: The existing task run.

    Returns:
        A summary row linking to the dedicated React run detail.
    """
    return row(
        job=cell(run.label, href=f"/ops/runs/{run.pk}/"),
        status=state(run.status),
        started=run.started_at or run.created_at,
        finished=run.finished_at,
        trigger=run.trigger,
    )


def login_row(event) -> OpsRow:
    """Exclude session keys and model authentication internals.

    Args:
        event: The recorded login event.

    Returns:
        A row containing only selected login metadata.
    """
    return row(
        time=event.created_at,
        username=event.username,
        kind=state(event.kind),
        address=event.ip_address,
        browser=event.user_agent,
    )


def _present_overview(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the overview workspace without serializing model internals.

    Args:
        request: The staff request containing presentation filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        The overview metrics, jobs, schedules, and recent run summaries.
    """
    c = context
    sections: list[OpsSection] = []
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    title = "Operations"
    sections.append(
        OpsSection(
            title="System health",
            details={
                "Overall": state(c["overall"]),
                "Checked at": cell(c["checked_at"]),
                "Users with sessions": cell(c["session_count"]),
            },
        )
    )
    for group, checks in c["groups"]:
        sections.append(
            OpsSection(
                title=group,
                table=table(
                    request,
                    [
                        row(
                            check=check.name,
                            status=state(check.status),
                            summary=check.summary,
                            detail=check.detail,
                            latency_ms=check.latency_ms,
                        )
                        for check in checks
                    ],
                ),
            )
        )
    for key, heading in (
        ("running", "Active runs (latest 8)"),
        ("recent_runs", "Recent runs (latest 8)"),
    ):
        sections.append(
            OpsSection(title=heading, table=table(request, [run_row(run) for run in c[key]]))
        )
    sections.append(
        OpsSection(
            title="Failed logins (top 6 addresses, 24 hours)",
            table=table(
                request,
                [
                    row(
                        address=entry["ip_address"],
                        failures=cell(
                            entry["count"], tone="negative" if entry["count"] else "neutral"
                        ),
                    )
                    for entry in c["failed_logins"]
                ],
            ),
        )
    )
    refresh = 15

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_jobs(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the jobs workspace without serializing model internals.

    Args:
        request: The staff request containing presentation filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        Job summaries and permission-aware action forms.
    """
    c = context
    sections: list[OpsSection] = []
    can_write = bool(getattr(request.user, "is_superuser", False))
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    entries = [entry for group in c["groups"].values() for entry in group]
    statistics = {entry["job"].run_label: entry["stats"] for entry in entries if entry["stats"]}
    totals = {
        key: sum(stats[key] for stats in statistics.values()) for key in ("runs", "ok", "failed")
    }
    sections.append(
        OpsSection(
            title="Job activity (last 7 days)",
            description="Success rate uses completed runs only. Active jobs is the current count.",
            details={
                "Configured jobs": cell(len(entries)),
                "Active jobs now": cell(sum(bool(entry["active"]) for entry in entries)),
                "Total runs": cell(totals["runs"]),
                "Succeeded": cell(totals["ok"], tone="positive" if totals["ok"] else "neutral"),
                "Failed": cell(
                    totals["failed"], tone="negative" if totals["failed"] else "neutral"
                ),
                "Success rate": _job_statistics(totals)["success_rate"],
            },
        )
    )
    for group, entries in c["groups"].items():
        rows = []
        for entry in entries:
            job = entry["job"]
            item = row(
                job=job.label,
                description=job.description,
                schedule="\n".join(entry["schedules"]) or "By hand only",
                next_run=entry["next_run"],
                last=state(entry["last"].status) if entry["last"] else "Never",
                **_job_statistics(entry["stats"]),
            )
            for key in ("last", "active"):
                if entry[key]:
                    item.links.append(link(f"{key.title()} run", f"runs/{entry[key].pk}/"))
            if can_write:
                item.forms.append(
                    action(
                        f"jobs/{job.key}/run/",
                        f"Run {job.label}",
                        fields=[
                            field(
                                "confirm",
                                "yes",
                                kind="checkbox",
                                label=job.confirm,
                                required=True,
                            )
                        ]
                        if job.confirm
                        else [],
                        disabled=bool(entry["active"]),
                    )
                )
            rows.append(item)
        sections.append(OpsSection(title=group, table=table(request, rows)))

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _job_statistics(stats: dict[str, Any] | None) -> dict[str, OpsCell]:
    """Format seven-day job counts and durations without exposing raw dictionaries.

    Args:
        stats: The existing task_stats aggregate, or no runs.

    Returns:
        Numeric sortable counts, a completed-run success rate, and readable durations.
    """
    values = stats or {}
    succeeded, failed = values.get("ok", 0), values.get("failed", 0)
    completed = succeeded + failed
    rate = round(100 * succeeded / completed) if completed else None
    return {
        "runs_7d": cell(values.get("runs", 0)),
        "succeeded": cell(succeeded, tone="positive" if succeeded else "neutral"),
        "failed": cell(failed, tone="negative" if failed else "neutral"),
        "success_rate": OpsCell(
            text=f"{rate}%" if rate is not None else "No completed runs",
            value=rate,
            tone="neutral" if rate is None else "positive" if not failed else "negative",
        ),
        "average_duration": OpsCell(
            text=duration(values.get("avg_ms")), value=values.get("avg_ms")
        ),
        "maximum_duration": OpsCell(
            text=duration(values.get("max_ms")), value=values.get("max_ms")
        ),
    }


def _present_logs(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the logs workspace without serializing model internals.

    Args:
        request: The staff request containing log filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        Bounded redacted log entries and live-refresh configuration.
    """
    c = context
    sections: list[OpsSection] = []
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    title = "Application logs"
    view = c["view"]
    description = (
        f"Redacted log tail: {view.path}. File size: {view.size_bytes} bytes. "
        f"{view.matched} matches in the bounded tail; at most 1000 entries."
        if view.exists
        else "There is no log file yet."
    )
    sections.append(
        OpsSection(
            title="Log entries",
            table=table(
                request,
                [
                    row(time=e.time, level=state(e.level), logger=e.logger, message=e.message)
                    for e in view.entries
                ],
                filters=("level", "logger"),
            ),
        )
    )
    refresh = 5 if c["live"] else 0

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_metrics(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the metrics workspace without serializing model internals.

    Args:
        request: The staff request containing presentation filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        Operational metrics, chart points, and corresponding data tables.
    """
    c = context
    sections: list[OpsSection] = []
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    for key, heading in (
        ("host", "Host"),
        ("redis", "Redis"),
        ("llm", "Sentiment scoring"),
        ("accuracy", "Prediction accuracy"),
    ):
        values = c[key]
        sections.append(
            OpsSection(
                title=heading,
                details={
                    key.replace("_", " ").title(): cell(value)
                    for key, value in (values or {}).items()
                },
                description="" if values else f"{heading} does not answer.",
            )
        )
    sections.append(
        OpsSection(
            title="Workers",
            description="" if c["workers"] else "No worker answers.",
            table=table(request, [row(**worker) for worker in (c["workers"] or [])]),
        )
    )
    sections.append(
        OpsSection(
            title="Jobs (7 days)",
            description=(
                "Success rate uses completed runs only; durations exclude runs without timings."
            ),
            table=table(
                request,
                [
                    row(
                        job=entry["label"],
                        **_job_statistics(entry),
                        last_started=entry["last_started"],
                    )
                    for entry in c["tasks"]
                ],
            ),
        )
    )
    sections.extend(
        OpsSection(
            title=chart["title"],
            description=chart.get("note", ""),
            chart=[
                OpsChartPoint(label=label, value=value, failed=failed)
                for label, value, failed in zip(
                    chart["labels"],
                    chart["values"],
                    chart.get("alerts", [0] * len(chart["labels"])),
                    strict=True,
                )
            ],
            table=table(
                request,
                [
                    row(
                        day=label,
                        value=value,
                        failed=cell(alert, tone="negative" if alert else "neutral"),
                    )
                    for label, value, alert in zip(
                        chart["labels"],
                        chart["values"],
                        chart.get("alerts", [0] * len(chart["labels"])),
                        strict=True,
                    )
                ],
            ),
        )
        for chart in c["charts"]
    )
    sections.append(
        OpsSection(
            title="Database",
            description=f"Size: {c['db_size']}",
            table=table(request, [row(table=name, records=count) for name, count in c["tables"]]),
        )
    )

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_invites(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present invitation metadata and superuser-only management controls."""
    can_write = bool(getattr(request.user, "is_superuser", False))
    rows = []
    for invite in context["invites"]:
        status = "Used" if invite.used_at else "Revoked" if invite.revoked else "Available"
        item = row(
            invitation=f"#{invite.pk}",
            state=cell(
                status,
                tone="positive"
                if status == "Available"
                else "negative"
                if status == "Revoked"
                else "neutral",
            ),
            created_at=invite.created_at,
            created_by=cell(
                invite.created_by.get_username() if invite.created_by else "Deleted user",
                href=f"/ops/users/{invite.created_by_id}/" if invite.created_by_id else "",
            ),
            used_at=invite.used_at,
            used_by=cell(
                invite.used_by.get_username() if invite.used_by else "",
                href=f"/ops/users/{invite.used_by_id}/" if invite.used_by_id else "",
            ),
            email=invite.used_by.email if invite.used_by else "",
        )
        if can_write and status == "Available":
            item.forms.append(
                action(
                    f"invites/{invite.pk}/revoke/",
                    "Revoke",
                    confirmation=f"Revoke invitation #{invite.pk}? It will no longer allow signup.",
                )
            )
        rows.append(item)
    invitations = table(request, rows, full=True, filters=("state",))
    if not invitations.columns:
        invitations.columns = [
            OpsColumn(key=key, label=label)
            for key, label in (
                ("invitation", "Invitation"),
                ("state", "State"),
                ("created_at", "Created At"),
                ("created_by", "Created By"),
                ("used_at", "Used At"),
                ("used_by", "Used By"),
                ("email", "Email"),
            )
        ]
    return OpsPage(
        title="Invite codes",
        description=(
            "Single-use sign-up invitations. Codes are shown only when generated; "
            "only their digests are stored. Staff can inspect details; only superusers can "
            "generate or revoke invitations."
        ),
        sections=[
            OpsSection(
                title="Invitations",
                description="Copy each new code from the success message and share it privately.",
                forms=[action("invites/generate/", "Generate invite code")]
                if can_write
                else [],
                table=invitations,
            )
        ],
    )


def _present_subscriptions(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present user and subscription lists without serializing model internals.

    Args:
        request: The staff request containing table filters.
        name: The allowlisted users or subscriptions view name.
        context: The context prepared by the original protected view.

    Returns:
        A server-processed user or subscription table.
    """
    c = context
    sections: list[OpsSection] = []
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    rows = []
    for entry in c["all_rows"] if name == "subscriptions" else c["rows"]:
        user = entry["user"]
        sub = entry["sub"]
        item = row(
            username=cell(user.get_username(), href=f"/ops/users/{user.pk}/"),
            email=user.email,
            role="Superuser" if user.is_superuser else "Staff" if user.is_staff else "Member",
            active=state("On" if user.is_active else "Off"),
            state=state(entry["state"]),
            ends=sub.ends_at if sub else None,
            days_left=entry["days_left"],
            removed_features=entry["removed"],
        )
        if name == "users":
            item.cells.update(
                sessions=cell(entry["sessions"]),
                logins=cell(user.login_count),
                failed_24h=cell(user.failed_24h),
                joined=cell(user.date_joined),
                last_login=cell(user.last_login),
            )
        rows.append(item)
    sections.append(
        OpsSection(
            title="Users" if name == "users" else "Subscriptions",
            table=table(request, rows, full=True, filters=("state", "role", "active")),
        )
    )
    if name == "subscriptions":
        sections.append(
            OpsSection(
                title="All-user subscription counts",
                details={label: cell(count) for _, label, count in c["counts"]},
            )
        )

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_user(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the user workspace without serializing model internals.

    Args:
        request: The staff request containing presentation filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        User details and protected actions with opaque session identifiers.
    """
    c = context
    sections: list[OpsSection] = []
    can_write = bool(getattr(request.user, "is_superuser", False))
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    user = c["subject"]
    pk = user.pk
    title = user.get_username()
    sections.append(
        OpsSection(
            title="Account",
            details={
                "Email": cell(user.email),
                "Role": cell(
                    "Superuser" if user.is_superuser else "Staff" if user.is_staff else "Member"
                ),
                "Active": state("On" if user.is_active else "Off"),
                "Joined": cell(user.date_joined),
                "Last login": cell(user.last_login),
                "Subscription": state(c["access"].state),
                "Subscription ends": cell(c["sub"].ends_at if c["sub"] else None),
                "Days left": cell(c["days_left"]),
            },
            forms=[
                action(
                    f"users/{pk}/active/",
                    f"Turn {user.get_username()} {'off' if user.is_active else 'on'}",
                    fields=[field("active", "no" if user.is_active else "yes")],
                    confirmation=(
                        "Change this user's ability to log in? Turning off ends their sessions."
                    ),
                ),
                action(
                    f"users/{pk}/sessions/end/",
                    "End all sessions",
                    confirmation="End all other sessions for this user?",
                ),
                action(
                    f"users/{pk}/tokens/revoke/",
                    "Revoke all API tokens",
                    confirmation="Revoke all active API tokens for this user?",
                ),
            ]
            if can_write
            else [],
        )
    )
    features = [
        row(
            feature=e["feature"].label,
            help=e["feature"].help,
            access=state("On" if e["allowed"] else "Removed"),
        )
        for e in c["feature_rows"]
    ]
    sections.append(
        OpsSection(
            title="Feature access",
            description=(
                "Staff always have all features; restrictions apply if staff access is removed."
            ),
            table=table(request, features),
            forms=[
                action(
                    f"users/{pk}/access/",
                    "Save features",
                    fields=[
                        OpsField(
                            name="allow",
                            label=e["feature"].label,
                            kind="checkbox",
                            value=e["feature"].key,
                            checked=e["allowed"],
                            help=e["feature"].help,
                        )
                        for e in c["feature_rows"]
                    ],
                )
            ]
            if can_write
            else [],
        )
    )
    sub_forms = []
    if can_write:
        sub_forms.append(
            form_data(
                c["give_form"], f"users/{pk}/subscription/give/", "Give or change subscription"
            )
        )
        if c["sub"] and c["access"].state not in {"expired", "staff"}:
            sub_forms.append(
                action(
                    f"users/{pk}/subscription/end/",
                    "End subscription now",
                    confirmation="End this subscription immediately?",
                )
            )
    sections.append(
        OpsSection(
            title="Subscription history (latest 10)",
            description=(
                f"Subscription requirement is {'ON' if c['require_subscription'] else 'OFF'}. "
                "Use days or an end date, not both."
            ),
            table=table(
                request,
                [
                    row(
                        action=e.get_action_display(),
                        kind=e.get_kind_display(),
                        ends=e.ends_at,
                        note=e.note,
                        time=e.created_at,
                        actor=e.actor_name,
                    )
                    for e in c["sub_events"]
                ],
            ),
            forms=sub_forms,
        )
    )
    session_rows = []
    for session in c["sessions"]:
        item = row(
            started=session.started,
            expires=session.expires,
            address=session.ip_address,
            browser=session.user_agent,
            current="Your session" if session.key == c["current_key"] else "",
        )
        if can_write and session.key != c["current_key"]:
            opaque = salted_hmac("ops-session-action", session.key, algorithm="sha256").hexdigest()
            item.forms.append(
                action(
                    f"users/{pk}/sessions/end/",
                    "End session",
                    fields=[field("session", opaque)],
                    confirmation="End this session?",
                )
            )
        session_rows.append(item)
    sections.append(OpsSection(title="Open sessions", table=table(request, session_rows)))
    token_rows = []
    for token in c["api_tokens"]:
        item = row(
            name=token.name,
            token=token.display,
            last_used=token.last_used_at,
            state=state(token.state),
        )
        if can_write and token.state == "active":
            item.forms.append(
                action(
                    f"users/{pk}/tokens/revoke/",
                    "Revoke token",
                    fields=[field("token", str(token.pk))],
                    confirmation="Revoke this API token?",
                )
            )
        token_rows.append(item)
    sections.append(
        OpsSection(title="API tokens (latest 20, masked)", table=table(request, token_rows))
    )
    for key, heading in (
        ("events", "Recent logins (latest 30)"),
        ("failed", "Failed logins (latest 10)"),
    ):
        sections.append(
            OpsSection(title=heading, table=table(request, [login_row(e) for e in c[key]]))
        )
    sections.append(
        OpsSection(
            title="Admin actions (latest 15)",
            table=table(
                request,
                [
                    row(
                        action=e.get_action_flag_display(),
                        object=e.object_repr,
                        type=e.content_type,
                        time=e.action_time,
                    )
                    for e in c["admin_actions"]
                ],
            ),
        )
    )
    sections.append(
        OpsSection(
            title="Ops actions (latest 15)",
            table=table(
                request,
                [
                    row(action=e.action, target=e.target, time=e.created_at)
                    for e in c["ops_actions"]
                ],
            ),
        )
    )
    sections.append(
        OpsSection(
            title="Triggered runs (latest 10)",
            table=table(request, [run_row(run) for run in c["runs"]]),
        )
    )

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_logins(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the logins workspace without serializing model internals.

    Args:
        request: The staff request containing time-window and table filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        Login statistics and a server-processed event table.
    """
    c = context
    sections: list[OpsSection] = []
    can_write = bool(getattr(request.user, "is_superuser", False))
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    title = "Logins and lockouts"
    # The React endpoint paginates the entire filtered queryset, not the legacy page.
    hours = request.GET.get("hours", "")
    events = users.login_events("", "", int(hours) if hours in {"24", "168", "720"} else None)
    sections.append(
        OpsSection(
            title="Login events",
            table=table(request, [login_row(e) for e in events], full=True, filters=("kind",)),
        )
    )
    sections.append(
        OpsSection(
            title="Failed logins (top 10 addresses, 24 hours)",
            table=table(
                request,
                [
                    row(
                        address=e["ip_address"],
                        failures=cell(e["count"], tone="negative" if e["count"] else "neutral"),
                    )
                    for e in c["failed_by_address"]
                ],
            ),
        )
    )
    rows = []
    for entry in c["lockouts"]:
        item = row(
            address=entry["ip_address"],
            usernames=", ".join(entry["usernames"]),
            failures=cell(entry["failures"], tone="negative" if entry["failures"] else "neutral"),
            last=entry["last"],
            until=entry["until"],
        )
        if can_write and entry["ip_address"]:
            item.forms.append(
                action(
                    "logins/unlock/",
                    "Unlock address",
                    fields=[field("ip_address", entry["ip_address"])],
                    confirmation="Allow this address to try signing in again?",
                )
            )
        rows.append(item)
    sections.append(OpsSection(title="Current lockouts", table=table(request, rows)))

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_config(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the configuration or settings index without serializing model internals.

    Args:
        request: The staff request containing presentation filters.
        name: The allowlisted config or settings view name.
        context: The context prepared by the original protected view.

    Returns:
        Configuration summaries or settings navigation.
    """
    c = context
    sections: list[OpsSection] = []
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    if name == "config":
        title = "Configuration"
        for heading, entries in c["sections"]:
            sections.append(
                OpsSection(
                    title=heading,
                    table=table(request, [row(setting=key, value=value) for key, value in entries]),
                )
            )
    else:
        sections.append(
            OpsSection(
                title="Setting groups",
                table=table(
                    request,
                    [
                        row(
                            group=cell(e["title"], href=f"/ops/settings/{e['key']}/"),
                            description=e["help"],
                            values=e["count"],
                            saved=e["saved"],
                        )
                        for e in c["groups"]
                    ],
                ),
            )
        )
        sections.append(
            OpsSection(
                title="Environment (read only)",
                table=table(request, [row(setting=key, value=value) for key, value in c["fixed"]]),
            )
        )

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_settings_group(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present a settings group without serializing model internals.

    Args:
        request: The staff request containing presentation filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        Permission-aware settings forms without stored password values.
    """
    c = context
    sections: list[OpsSection] = []
    can_write = bool(getattr(request.user, "is_superuser", False))
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    title, description = c["title"], c["help"]
    rows = [
        row(
            setting=e["spec"].label,
            key=e["spec"].key,
            current=e["text"],
            default=e["default"],
            source="Saved override" if e["saved"] else "Environment",
        )
        for e in c["rows"]
    ]
    section = OpsSection(title="Settings", table=table(request, rows))
    if can_write:
        help_by_name = {e["spec"].key: e["spec"].help for e in c["rows"]}
        edit = form_data(
            c["form"], f"settings/{c['group']}/", "Save settings", help_by_name=help_by_name
        )
        allowed = {e["reset"].html_name for e in c["rows"] if e["saved"]}
        edit.fields = [
            f for f in edit.fields if not f.name.startswith("reset__") or f.name in allowed
        ]
        section.forms.append(edit)
        section.forms.extend(
            action(
                f"jobs/{job.key}/run/",
                job.label,
                fields=[field("confirm", "yes", kind="checkbox", label=job.confirm, required=True)]
                if job.confirm
                else [],
            )
            for job in c["telegram_jobs"]
        )
    sections.append(section)

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_schedule(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the schedule workspace without serializing model internals.

    Args:
        request: The staff request containing table filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        A server-processed schedule table and protected actions.
    """
    c = context
    sections: list[OpsSection] = []
    can_write = bool(getattr(request.user, "is_superuser", False))
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    title = "Schedule"
    rows = []
    for entry in c["rows"]:
        schedule = entry["entry"]
        item = row(
            entry=schedule.name,
            job=entry["label"],
            cron=schedule.cron_text,
            timezone=schedule.timezone,
            next=entry["next_run"],
            state=state("On" if schedule.enabled else "Off"),
            last=cell(entry["last"].status, href=f"/ops/runs/{entry['last'].pk}/")
            if entry["last"]
            else "Never",
        )
        if can_write:
            if entry["managed_backup"]:
                item.links.append(link("Manage backups", "backups/"))
            else:
                item.links.append(link("Edit schedule", f"schedule/{schedule.pk}/"))
                item.forms.extend(
                    [
                        action(
                            f"schedule/{schedule.pk}/toggle/",
                            "Turn off" if schedule.enabled else "Turn on",
                        ),
                        action(
                            f"schedule/{schedule.pk}/delete/",
                            "Delete schedule",
                            confirmation=f"Delete {schedule.name}?",
                        ),
                    ]
                )
        rows.append(item)
    sections.append(
        OpsSection(
            title="Schedule entries",
            description=(
                "Cron: minute hour day-of-month month day-of-week. "
                "Times use each entry's time zone."
            ),
            table=table(request, rows, full=True, filters=("state",)),
            links=[link("Add entry", "schedule/add/")] if can_write else [],
            forms=[
                action(
                    "schedule/reset/",
                    "Reset to default",
                    fields=[
                        field(
                            "confirm",
                            "yes",
                            kind="checkbox",
                            label="Replace my schedule with the default schedule",
                            required=True,
                        )
                    ],
                )
            ]
            if can_write
            else [],
        )
    )

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_schedule_add(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present schedule creation or editing without serializing model internals.

    Args:
        request: The staff request containing presentation filters.
        name: The allowlisted schedule creation or editing view name.
        context: The context prepared by the original protected view.

    Returns:
        The original schedule form's fields, values, and validation errors.
    """
    c = context
    sections: list[OpsSection] = []
    can_write = bool(getattr(request.user, "is_superuser", False))
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    title = "Edit schedule" if c["entry"] else "Add schedule"
    sections.append(
        OpsSection(
            title=title,
            forms=[
                form_data(
                    c["form"],
                    f"schedule/{c['entry'].pk}/" if c["entry"] else "schedule/add/",
                    "Save schedule",
                )
            ]
            if can_write
            else [],
            details={} if can_write else {str(f.label): cell(f.value()) for f in c["form"]},
            links=[link("All schedules", "schedule/")],
        )
    )
    sections.append(
        OpsSection(
            title="Upcoming runs",
            table=table(request, [row(time=value) for value in c["upcoming"]]),
        )
    )

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_feeds(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the feeds workspace without serializing model internals.

    Args:
        request: The staff request containing table filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        A server-processed feed table and protected management forms.
    """
    c = context
    sections: list[OpsSection] = []
    can_write = bool(getattr(request.user, "is_superuser", False))
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    title = "News feeds"
    rows = []
    for feed in c["feeds"]:
        item = row(
            source=feed.source,
            name=feed.name,
            url=feed.url,
            last_fetched=feed.last_fetched_at,
            new=feed.last_new_count,
            error=feed.last_error,
            state=state("On" if feed.enabled else "Off"),
        )
        if can_write:
            item.forms.extend(
                [
                    action(f"feeds/{feed.pk}/toggle/", "Turn off" if feed.enabled else "Turn on"),
                    action(
                        f"feeds/{feed.pk}/delete/",
                        "Delete feed",
                        confirmation="Delete this feed? Its articles stay.",
                    ),
                ]
            )
        rows.append(item)
    sections.append(
        OpsSection(
            title="Feeds",
            table=table(request, rows, full=True, filters=("source", "state")),
            forms=[form_data(c["form"], "feeds/", "Add feed")] if can_write else [],
        )
    )

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_instruments(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the instruments workspace without serializing model internals.

    Args:
        request: The staff request containing table filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        A server-processed instrument table and protected management forms.
    """
    c = context
    sections: list[OpsSection] = []
    can_write = bool(getattr(request.user, "is_superuser", False))
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    title = "Market instruments"
    rows = []
    for entry in c["rows"]:
        instrument = entry["instrument"]
        item = row(
            symbol=instrument.symbol,
            name=instrument.name,
            kind=instrument.kind,
            weight=instrument.weight,
            scale=instrument.scale,
            state=state("On" if instrument.enabled else "Off"),
        )
        if can_write:
            item.forms.append(
                form_data(
                    entry["form"], f"instruments/{instrument.pk}/", f"Save {instrument.symbol}"
                )
            )
            if instrument.kind != "target":
                item.forms.append(
                    action(
                        f"instruments/{instrument.pk}/delete/",
                        "Delete instrument",
                        confirmation="Delete this instrument? Old quotes stay.",
                    )
                )
        rows.append(item)
    sections.append(
        OpsSection(
            title="Instruments",
            description=(
                f"Total absolute enabled cue weight: {c['weight_total']}. "
                "The target index cannot be removed or disabled."
            ),
            table=table(request, rows, full=True, filters=("kind", "state")),
            forms=[form_data(c["add_form"], "instruments/", "Add instrument")] if can_write else [],
        )
    )

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def _present_backups(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Present the backups workspace without serializing model internals.

    Args:
        request: The superuser request containing presentation filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        Backup settings, export actions, and confirmed destructive restore forms.
    """
    c = context
    sections: list[OpsSection] = []
    title = name.replace("_", " ").title()
    description = (
        "Staff can inspect operations. Only superusers can make changes. Times are shown in IST."
    )
    refresh = 0
    title = "Database backups"
    description = (
        "Superusers only. Snapshots include all records, password hashes, sessions, "
        "API token hashes, and encrypted settings. Store them securely. "
        "Files, environment, encryption keys, and models "
        "are not included. Restore requires the same schema and encryption keys. "
        "Use a maintenance window: stop workers, Beat, and other writers before restoring; "
        "restart services afterwards to clear cached settings. "
        "For large databases use native backups."
    )
    sections.append(
        OpsSection(
            title="Automated encrypted backups",
            description=(
                "Set BACKUP_ENCRYPTION_KEY in web and worker environments; keep it separately. "
                "Celery Beat and a worker must run. Local folders must already exist and be "
                "writable in the worker. External S3 requires HTTPS; bundled Silo permits "
                "http://silo:9000, bucket kashengine-backups, region us-east-1. "
                "Use upload-only credentials, never root credentials. Saved credentials "
                "are never displayed. All files are retained; configure retention at "
                "your storage provider."
            ),
            forms=[
                form_data(c["backup_form"], "backups/settings/", "Save backup settings"),
                action(
                    "backups/run/",
                    "Run configured backup now",
                    disabled=not c["backup_config"].enabled,
                ),
            ],
            links=[link("Last backup run", f"runs/{c['last_backup'].pk}/")]
            if c["last_backup"]
            else [],
        )
    )
    sections.append(
        OpsSection(
            title="Manual snapshot",
            description=(
                "Snapshots can migrate SQLite/PostgreSQL when schemas and keys match. "
                "Consistent exports may briefly block writes."
            ),
            forms=[action("backups/export/", "Download database snapshot", download=True)],
        )
    )
    sections.append(
        OpsSection(
            title="Replace entire database",
            description=(
                "This deletes and replaces ALL current records; it does not merge. "
                "Failed restores roll back. Take a fresh backup first. "
                "Maximum snapshot: 100 MiB (140 MiB encrypted). JSON and .json.enc are accepted. "
                "Success signs this browser out; sign in with a restored account."
            ),
            forms=[
                action(
                    "backups/import/",
                    "Replace entire database",
                    fields=[
                        field("backup", "", kind="file", label="Database snapshot", required=True),
                        field(
                            "confirmation",
                            "",
                            kind="text",
                            label="Type RESTORE to replace all database records",
                            required=True,
                        ),
                    ],
                    confirmation=(
                        "Replace the entire database? Stop all other database writers "
                        "and take a fresh backup first."
                    ),
                )
            ],
        )
    )

    return OpsPage(title=title, description=description, sections=sections, refresh_seconds=refresh)


def page_data(request: HttpRequest, name: str, context: dict[str, Any]) -> OpsPage:
    """Dispatch only explicitly registered page presenters.

    Args:
        request: The authorized request containing presentation filters.
        name: The resolved allowlisted Ops view name.
        context: The context prepared by the original protected view.

    Returns:
        A typed page containing only explicitly selected presentation data.

    Raises:
        Http404: If no presenter is registered for the view.
    """
    presenters = {
        "overview": _present_overview,
        "jobs": _present_jobs,
        "logs": _present_logs,
        "metrics": _present_metrics,
        "subscriptions": _present_subscriptions,
        "users": _present_subscriptions,
        "invites": _present_invites,
        "user": _present_user,
        "logins": _present_logins,
        "config": _present_config,
        "settings": _present_config,
        "settings_group": _present_settings_group,
        "schedule": _present_schedule,
        "schedule_add": _present_schedule_add,
        "schedule_edit": _present_schedule_add,
        "feeds": _present_feeds,
        "instruments": _present_instruments,
        "backups": _present_backups,
    }
    presenter = presenters.get(name)
    if presenter is None:
        raise Http404
    return presenter(request, name, context)


def target(path: str, allowed: set[str]):
    """Resolve only canonical Ops URLs in a fixed view-name allowlist.

    Args:
        path: The relative Ops page or action path.
        allowed: The permitted Ops view names for this dispatcher.

    Returns:
        The matching original Ops view and its URL arguments.

    Raises:
        Http404: If the path is noncanonical, unresolved, or outside the allowlist.
    """
    if "?" in path or "#" in path or "//" in path or ".." in path or "\\" in path:
        raise Http404
    path = "" if path == "overview/" else path
    try:
        match = resolve(f"/ops/{path}", urlconf="config.legacy_urls")
    except Resolver404 as exc:
        raise Http404 from exc
    if match.namespace != "ops" or match.url_name not in allowed:
        raise Http404
    return match


def workspace_redirect(url: str) -> str:
    """Keep action outcomes within React, except the restore's login redirect.

    Args:
        url: The redirect destination returned by the original action.

    Returns:
        The equivalent React destination or the post-restore login path.

    Raises:
        ValueError: If the original action returns an unexpected destination.
    """
    if url.startswith("/ops/"):
        return url
    if url == "/login/":
        return url
    raise ValueError(f"Unexpected Ops action redirect: {url}")


@router.get(
    "/ops/pages/{path:path}",
    response={200: OpsPage, **ERRORS_WITH_VALIDATION},
    operation_id="get_app_ops_page",
    summary="Read an Ops workspace page",
)
def get_page(request: HttpRequest, path: str):
    """Reuse the legacy view's context without rendering HTML or serializing models."""
    match = target(path, PAGES)
    response = match.func(request, **match.kwargs)
    if not isinstance(response, TemplateResponse):
        # The managed backup schedule deliberately redirects to its owner.
        if response.status_code == HTTPStatus.FOUND:
            return OpsPage(
                title="Managed backup schedule",
                sections=[
                    OpsSection(
                        title="Managed backup schedule",
                        links=[
                            NavigationItem(
                                label="Manage backup schedule",
                                url=workspace_redirect(response["Location"]),
                            )
                        ],
                    )
                ],
            )
        raise TypeError("Ops page did not provide a template context.")
    return page_data(request, match.url_name, response.context_data)


@router.post(
    "/ops/actions/{path:path}",
    response={200: OpsActionResult, **ERRORS_WITH_VALIDATION},
    operation_id="post_app_ops_action",
    summary="Perform an existing superuser Ops action",
)
@superuser_required
def post_action(request: HttpRequest, path: str):
    """Keep domain validation/auditing in the original handler; return explicit outcomes."""
    match = target(path, ACTIONS)
    if match.url_name == "user_end_sessions" and request.POST.get("key"):
        raise PermissionDenied("Use an opaque session identifier.")
    response = match.func(request, **match.kwargs)
    if getattr(response, "streaming", False):
        return response
    notices = list(get_messages(request))
    feedback = [OpsMessage(level=m.level_tag, text=str(m)) for m in notices]
    if isinstance(response, TemplateResponse):
        name = "backups" if match.url_name == "backup_settings" else match.url_name
        return OpsActionResult(
            ok=False, messages=feedback, page=page_data(request, name, response.context_data)
        )
    if response.status_code != HTTPStatus.FOUND:
        raise TypeError("Ops action did not provide a recognized response.")
    return OpsActionResult(
        ok=not any(m.level >= ERROR for m in notices),
        messages=feedback,
        redirect=workspace_redirect(response["Location"]),
    )
