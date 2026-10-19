"""Superuser-only download and replacement restore controls."""

import logging
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.db import DatabaseError
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from . import backup_automation, backups, jobs
from .backup_forms import BackupConfigurationForm
from .models import TaskRun
from .permissions import superuser_post_required, superuser_required

logger = logging.getLogger(__name__)


@never_cache
@superuser_required
def backup_page(request: HttpRequest) -> HttpResponse:
    """Show the warnings and download/upload controls.

    Args:
        request: The authorized superuser's request.

    Returns:
        The backups page, or a method-not-allowed response.
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    return _render_page(request)


def _render_page(request: HttpRequest, form=None, *, status: int = 200) -> HttpResponse:
    """Render configuration and the latest task result without exposing saved credentials.

    Args:
        request: The authorized superuser's request.
        form: A bound invalid form, or None for the saved settings.
        status: The HTTP response status.

    Returns:
        The rendered backups page.
    """
    config = backup_automation.configuration()
    return TemplateResponse(
        request,
        "ops/backups.html",
        {
            "section": "backups",
            "backup_form": form if form is not None else BackupConfigurationForm(instance=config),
            "backup_config": config,
            "last_backup": TaskRun.objects.filter(task_name=backup_automation.TASK_NAME).first(),
        },
        status=status,
    )


@never_cache
@superuser_post_required
def backup_settings(request: HttpRequest) -> HttpResponse:
    """Configure a daily backup without exposing saved credentials.

    Args:
        request: The superuser's configuration POST.

    Returns:
        A redirect after saving, or the form with validation errors.
    """
    form = BackupConfigurationForm(request.POST, instance=backup_automation.configuration())
    if not form.is_valid():
        return _render_page(request, form, status=400)
    form.save_for(request.user)
    messages.success(request, "Backup settings saved.")
    return redirect("ops:backups")


@never_cache
@superuser_post_required
def backup_run(request: HttpRequest) -> HttpResponse:
    """Queue a configured encrypted backup in the network-enabled worker.

    Args:
        request: The superuser's run-now POST.

    Returns:
        A redirect with a queued, disabled, busy, or dispatch-failure notification.
    """
    if not backup_automation.configuration().enabled:
        messages.error(request, "Enable and configure backups before running a backup.")
        return redirect("ops:backups")
    try:
        jobs.start_job(jobs.JOBS_BY_KEY["database-backup"], request.user, request=request)
    except (jobs.JobBusyError, jobs.JobDispatchError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Backup queued. Check the run history for its result.")
    return redirect("ops:backups")


@never_cache
@superuser_post_required
def backup_export(request: HttpRequest) -> HttpResponse | FileResponse:
    """Download a sensitive database snapshot, never a cacheable response.

    Args:
        request: The superuser's export POST.

    Returns:
        An attachment response, or a redirect with an explicit failure notification.
    """
    try:
        payload = backups.export_database(request.user)
    except (backups.BackupError, DatabaseError):
        logger.exception("Database export failed.")
        messages.error(request, "Database export failed. Check the server logs.")
        return redirect("ops:backups")
    response = FileResponse(
        BytesIO(payload),
        as_attachment=True,
        filename=f"kashengine-{timezone.now():%Y%m%dT%H%M%SZ}.json",
        content_type="application/json",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
@superuser_post_required
def backup_import(request: HttpRequest) -> HttpResponse:
    """Restore a bounded upload and end this browser's session after success.

    Args:
        request: The superuser's multipart upload and confirmation POST.

    Returns:
        A login redirect after success, or a backups redirect with the error.
    """
    upload = request.FILES.get("backup")
    if upload is None:
        messages.error(request, "Choose a database snapshot.")
        return redirect("ops:backups")
    try:
        backups.restore_database(
            upload.read(backups.MAX_BACKUP_FILE_BYTES + 1),
            request.user,
            confirmation=request.POST.get("confirmation", ""),
        )
    except backups.BackupError as exc:
        logger.warning("Database import rejected: %s", exc)
        messages.error(request, str(exc))
        return redirect("ops:backups")
    except DatabaseError:
        logger.exception("Database import could not read the current schema.")
        messages.error(request, "Database import failed. Check the server logs.")
        return redirect("ops:backups")
    # Do not send logout signals with an actor from the replaced database.
    request.session.flush()
    request.user = AnonymousUser()
    messages.success(request, "Database restored. Sign in using an account from the snapshot.")
    return redirect("web:login")
