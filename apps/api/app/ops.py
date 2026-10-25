"""Staff-only operational histories; reading never dispatches jobs or writes audit events."""

from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Query, Router

from apps.api.errors import ApiError
from apps.api.v1.common import ERRORS_WITH_NOT_FOUND, ERRORS_WITH_VALIDATION
from apps.ops import audit
from apps.ops.models import AuditEvent, TaskRun
from apps.ops.templatetags.ops_extras import duration
from apps.siteconfig import conf

from .auth import OpsSession
from .schemas import OpsAuditPage, OpsRunDetail, OpsRunPage, OpsRunSummary
from .tables import TableFilters, ordered

router = Router(tags=["Ops"], auth=OpsSession())


class AuditFilters(TableFilters):
    """Bound audit search, exact actor/action filters, and display-column sorts."""

    q: str = Field(default="", max_length=200)
    actor: str = Field(default="", max_length=150)
    action: str = Field(default="", max_length=50)
    sort: str = Field(default="", pattern="^(|-?(created_at|actor_name|action|target|ip_address))$")


@router.get(
    "/ops/audit",
    response={200: OpsAuditPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_ops_audit",
    summary="Search the audit trail as staff",
)
def list_audit(request: HttpRequest, filters: Query[AuditFilters]):
    """Search all retained audit records before pagination, without changing them.

    Args:
        request: The authenticated staff request.
        filters: Search, recorded actor, action, sorting, and pagination.

    Returns:
        Legacy audit display fields with global actor/action choices and page metadata.
    """
    events = AuditEvent.objects.all()
    if query := filters.q.strip():
        events = events.filter(
            Q(actor_name__icontains=query)
            | Q(action__icontains=query)
            | Q(target__icontains=query)
            | Q(detail__icontains=query)
            | Q(ip_address__icontains=query)
        )
    if filters.actor:
        events = events.filter(actor_name=filters.actor)
    if filters.action:
        events = events.filter(action=filters.action)
    events = ordered(
        events,
        filters.sort,
        {field: field for field in ("created_at", "actor_name", "action", "target", "ip_address")},
    )
    page = Paginator(events, filters.page_size or conf.OPS_PAGE_SIZE).get_page(max(1, filters.page))
    return {
        "items": list(page.object_list),
        "page": page.number,
        "pages": page.paginator.num_pages,
        "total": page.paginator.count,
        "page_size": page.paginator.per_page,
        "actors": list(
            AuditEvent.objects.exclude(actor_name="")
            .order_by("actor_name")
            .values_list("actor_name", flat=True)
            .distinct()
        ),
        "actions": list(
            AuditEvent.objects.exclude(action="")
            .order_by("action")
            .values_list("action", flat=True)
            .distinct()
        ),
    }


class RunFilters(TableFilters):
    """Bound search, exact legacy filters, and display-column sorts."""

    q: str = Field(default="", max_length=200)
    label: str = Field(default="", max_length=200)
    status: str = Field(default="", pattern="^(|pending|started|success|failure)$")
    trigger: str = Field(default="", pattern="^(|auto|manual)$")
    sort: str = Field(default="", pattern="^(|-?(label|started_at|duration_ms|trigger|status))$")


def run_summary(run: TaskRun) -> OpsRunSummary:
    """Keep history rows small, excluding output and diagnostics.

    Args:
        run: A task run with its triggering user selected.

    Returns:
        The legacy table's display values and raw sortable timestamps/duration.
    """
    return OpsRunSummary(
        id=run.pk,
        label=run.label,
        status=run.status,
        status_label=run.get_status_display(),  # ty: ignore[unresolved-attribute]
        trigger=run.trigger,
        triggered_by=run.triggered_by.get_username() if run.triggered_by else None,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=run.duration_ms,
        duration=duration(run.duration_ms),
        is_active=run.is_active,
    )


@router.get(
    "/ops/runs",
    response={200: OpsRunPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_ops_runs",
    summary="Search task runs as staff",
)
def list_runs(request: HttpRequest, filters: Query[RunFilters]):
    """Filter and sort all retained runs before pagination.

    Args:
        request: The authenticated staff request.
        filters: Search, job, status, trigger, sort, and pagination.

    Returns:
        A bounded page, all job choices, and the configured retention period.
    """
    runs = TaskRun.objects.select_related("triggered_by").defer("args", "result", "error", "output")
    if query := filters.q.strip():
        runs = runs.filter(
            Q(label__icontains=query)
            | Q(task_name__icontains=query)
            | Q(task_id__icontains=query)
            | Q(triggered_by__username__icontains=query)
        )
    for name in ("label", "status", "trigger"):
        if value := getattr(filters, name):
            runs = runs.filter(**{name: value})
    runs = runs.annotate(display_started_at=Coalesce("started_at", "created_at"))
    runs = ordered(
        runs,
        filters.sort,
        {
            "label": "label",
            "started_at": "display_started_at",
            "duration_ms": "duration_ms",
            "trigger": "trigger",
            "status": "status",
        },
    )
    page = Paginator(runs, filters.page_size or conf.OPS_PAGE_SIZE).get_page(max(1, filters.page))
    return {
        "items": [run_summary(run) for run in page.object_list],
        "page": page.number,
        "pages": page.paginator.num_pages,
        "total": page.paginator.count,
        "page_size": page.paginator.per_page,
        "labels": list(
            TaskRun.objects.order_by("label").values_list("label", flat=True).distinct()
        ),
        "retention_days": conf.OPS_RETENTION_DAYS,
    }


@router.post(
    "/ops/runs/{pk}/stop",
    response={200: dict, **ERRORS_WITH_NOT_FOUND},
    operation_id="stop_app_ops_run",
    summary="Stop an active task run as a superuser",
)
def stop_run(request: HttpRequest, pk: int):
    """Stop a pending or started task run and mark it failed.

    The request is allowed only for superusers, like every change in Ops. The Celery worker is
    instructed to terminate the task so the app does not leave a hung task in the queue. The
    action is written to the audit trail.
    """
    if not getattr(request.user, "is_superuser", False):
        raise ApiError("feature_not_available", "Only a superuser can stop a task run.")
    run = get_object_or_404(TaskRun, pk=pk)
    if not run.is_active:
        return {"ok": False, "status": run.status}
    from config.celery import app  # noqa: PLC0415

    app.control.revoke(run.task_id, terminate=True, signal="SIGKILL")
    now = timezone.now()
    run.status = TaskRun.Status.FAILURE
    run.finished_at = now
    if run.started_at:
        run.duration_ms = max(0, int((now - run.started_at).total_seconds() * 1000))
    else:
        run.duration_ms = 0
    run.error = run.error or "The run was stopped by an admin."
    run.save(update_fields=["status", "finished_at", "duration_ms", "error"])
    audit.record(request.user, "stop run", run.label, f"run {run.pk}", request)
    return {"ok": True, "status": run.status}


@router.get(
    "/ops/runs/{pk}",
    response={200: OpsRunDetail, **ERRORS_WITH_NOT_FOUND},
    operation_id="get_app_ops_run",
    summary="Read one task run and its diagnostics as staff",
)
def get_run(request: HttpRequest, pk: int):
    """Read stored diagnostics with the same permissions as the legacy run detail.

    Args:
        request: The authenticated staff request.
        pk: Task-run primary key.

    Returns:
        Summary fields, task identity, worker, arguments, result, error, and output.

    Raises:
        Http404: If the run does not exist.
    """
    run = get_object_or_404(TaskRun.objects.select_related("triggered_by"), pk=pk)
    return OpsRunDetail(
        **run_summary(run).model_dump(),
        task_id=run.task_id,
        task_name=run.task_name,
        worker=run.worker,
        args=run.args,
        result=run.result,
        error=run.error,
        output=run.output,
    )
