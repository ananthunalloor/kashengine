"""Pages where a superuser changes the settings, the schedule, the feeds, and the instruments.

Staff users can look. Only a superuser can save (POST). Every change goes in the audit trail.
Secrets are never shown. The page shows only if a secret is set.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from apps.markets.models import Instrument
from apps.news.models import NewsFeed
from apps.siteconfig import conf, registry
from apps.siteconfig import service as site_service

from . import audit, configview, jobs, schedule
from .forms import (
    RESET_PREFIX,
    FeedForm,
    InstrumentForm,
    ScheduleForm,
    settings_form,
)
from .models import TaskRun
from .permissions import staff_required, superuser_post_required

MAX_DETAIL_CHARS = 120
TELEGRAM_JOBS = ("telegram-check", "telegram-test")


def _is_superuser(request: HttpRequest) -> bool:
    return bool(getattr(request.user, "is_superuser", False))


def _short(value: object) -> str:
    text = str(value)
    return text if len(text) <= MAX_DETAIL_CHARS else text[: MAX_DETAIL_CHARS - 1] + "…"


# Settings


@staff_required
def settings_index(request: HttpRequest) -> HttpResponse:
    """The groups of settings, with the number of values that were saved on the dashboard."""
    saved = conf.overrides()
    groups = [
        {
            "key": key,
            "title": title,
            "help": help_text,
            "count": len(registry.specs_in(key)),
            "saved": sum(1 for spec in registry.specs_in(key) if spec.key in saved),
        }
        for key, title, help_text in registry.GROUPS
    ]
    fixed = [
        (name, text)
        for title, rows in configview.sections()
        if title in {"Environment", "Security", "Queue"}
        for name, text in rows
    ]
    context = {"groups": groups, "fixed": fixed, "section": "settings"}
    return render(request, "ops/settings_index.html", context)


def _rows(form, specs: list[registry.Spec]) -> list[dict]:
    saved = conf.overrides()
    rows = []
    for spec in specs:
        current = conf.get(spec.key)
        rows.append(
            {
                "spec": spec,
                "field": form[spec.key],
                "reset": form[RESET_PREFIX + spec.key],
                "saved": spec.key in saved,
                "is_set": bool(current) if spec.secret else None,
                "text": configview.display_value(spec.key, current),
                "default": configview.display_value(spec.key, conf.default(spec.key)),
            }
        )
    return rows


def _initial(specs: list[registry.Spec]) -> dict:
    initial = {}
    for spec in specs:
        if spec.secret:
            continue
        value = conf.get(spec.key)
        initial[spec.key] = "\n".join(value) if isinstance(value, list) else value
    return initial


@staff_required
def settings_group(request: HttpRequest, group: str) -> HttpResponse:
    """One group of settings. A superuser can save them."""
    if group not in registry.GROUP_TITLES:
        raise Http404
    specs = registry.specs_in(group)
    form_class = settings_form(group)
    if request.method == "POST":
        if not _is_superuser(request):
            raise PermissionDenied
        form = form_class(request.POST)
        if form.is_valid():
            return _save_group(request, group, specs, form)
        messages.error(request, "Nothing was saved. Fix the marked fields.")
    else:
        form = form_class(initial=_initial(specs))
    context = {
        "group": group,
        "title": registry.GROUP_TITLES[group],
        "help": next(text for key, _t, text in registry.GROUPS if key == group),
        "rows": _rows(form, specs),
        "form": form,
        "section": "settings",
        "telegram_jobs": [jobs.JOBS_BY_KEY[key] for key in TELEGRAM_JOBS]
        if group == "telegram"
        else [],
    }
    return render(request, "ops/settings_group.html", context)


def _save_group(request: HttpRequest, group: str, specs, form) -> HttpResponse:
    resets = [s.key for s in specs if form.cleaned_data.get(RESET_PREFIX + s.key)]
    values = {s.key: form.cleaned_data[s.key] for s in specs if s.key not in resets}
    before = {s.key: conf.get(s.key) for s in specs}
    changed = site_service.save(values, request.user)
    reset = [key for key in resets if conf.is_saved(key)]
    site_service.reset(resets)
    details = []
    for key in changed:
        if registry.SPECS[key].secret:
            details.append(f"{key}: changed")
        else:
            details.append(f"{key}: {_short(before[key])} -> {_short(conf.get(key))}")
    details.extend(f"{key}: back to the default" for key in reset)
    if details:
        audit.record(
            request.user,
            "change settings",
            registry.GROUP_TITLES[group],
            "\n".join(details),
            request,
        )
        messages.success(request, f"Saved {len(details)} change(s).")
    else:
        messages.info(request, "No change.")
    return redirect("ops:settings_group", group=group)


# Schedule


@staff_required
def schedule_list(request: HttpRequest) -> HttpResponse:
    """All schedule entries with their next run and their last run."""
    now = timezone.now()
    labels = schedule.schedulable_tasks()
    last_runs = {
        run.label: run
        for run in TaskRun.objects.filter(
            trigger=TaskRun.Trigger.AUTO, task_name__in=labels
        ).order_by("created_at")
    }
    rows = []
    for entry in schedule.entries(enabled_only=False):
        upcoming = schedule.next_after(entry.schedule, now) if entry.enabled else None
        rows.append(
            {
                "entry": entry,
                "label": labels.get(entry.task, entry.task),
                "next_run": upcoming,
                "last": last_runs.get(entry.task),
            }
        )
    return render(request, "ops/schedule.html", {"rows": rows, "section": "schedule"})


def _schedule_form_page(request: HttpRequest, pk: int | None) -> HttpResponse:
    entry = next((e for e in schedule.entries(enabled_only=False) if e.pk == pk), None)
    if pk is not None and entry is None:
        raise Http404
    initial = (
        {
            "name": entry.name,
            "task": entry.task,
            "minute": entry.minute,
            "hour": entry.hour,
            "day_of_week": entry.day_of_week,
            "day_of_month": entry.day_of_month,
            "month": entry.month_of_year,
            "enabled": entry.enabled,
        }
        if entry
        else None
    )
    form = ScheduleForm(request.POST or None, initial=initial)
    if request.method == "POST":
        if not _is_superuser(request):
            raise PermissionDenied
        if form.is_valid():
            data = form.cleaned_data
            try:
                schedule.save_entry(pk, **data)
            except ValueError as exc:
                form.add_error(None, str(exc))
            else:
                action = "change schedule" if entry else "add schedule"
                audit.record(
                    request.user,
                    action,
                    data["name"],
                    f"{data['task']}: {data['minute']} {data['hour']} {data['day_of_month']} "
                    f"{data['month']} {data['day_of_week']}, enabled={data['enabled']}",
                    request,
                )
                messages.success(
                    request, "The schedule is saved. Beat picks it up in a few seconds."
                )
                return redirect("ops:schedule")
    upcoming = []
    if form.is_bound and form.is_valid():
        data = form.cleaned_data
        cron = schedule.parse_cron(
            data["minute"], data["hour"], data["day_of_week"], data["day_of_month"], data["month"]
        )
        upcoming = schedule.preview(cron, timezone.now())
    elif entry:
        upcoming = schedule.preview(entry.schedule, timezone.now())
    context = {"form": form, "entry": entry, "upcoming": upcoming, "section": "schedule"}
    return render(request, "ops/schedule_form.html", context)


@staff_required
def schedule_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Change one entry."""
    return _schedule_form_page(request, pk)


@staff_required
def schedule_add(request: HttpRequest) -> HttpResponse:
    """Add an entry."""
    return _schedule_form_page(request, None)


@superuser_post_required
def schedule_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """Turn an entry on or off."""
    entry = next((e for e in schedule.entries(enabled_only=False) if e.pk == pk), None)
    if entry is None:
        raise Http404
    schedule.save_entry(
        pk,
        name=entry.name,
        task=entry.task,
        minute=entry.minute,
        hour=entry.hour,
        day_of_week=entry.day_of_week,
        day_of_month=entry.day_of_month,
        month=entry.month_of_year,
        enabled=not entry.enabled,
    )
    state = "off" if entry.enabled else "on"
    audit.record(request.user, f"turn {state} schedule", entry.name, "", request)
    messages.success(request, f"{entry.name} is now {state}.")
    return redirect("ops:schedule")


@superuser_post_required
def schedule_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete an entry."""
    row = get_object_or_404(PeriodicTask, pk=pk)
    name = row.name
    row.delete()
    audit.record(request.user, "delete schedule", name, "", request)
    messages.success(request, f"{name} is deleted.")
    return redirect("ops:schedule")


@superuser_post_required
def schedule_reset(request: HttpRequest) -> HttpResponse:
    """Put the default schedule back."""
    if request.POST.get("confirm") != "yes":
        messages.error(request, "Tick the box to confirm. This replaces your schedule.")
        return redirect("ops:schedule")
    count = schedule.reset_to_default()
    audit.record(request.user, "reset schedule", "all", f"{count} default entries", request)
    messages.success(request, "The default schedule is back.")
    return redirect("ops:schedule")


# Feeds


@staff_required
def feed_list(request: HttpRequest) -> HttpResponse:
    """The news feeds and the result of their last run. A superuser can add one."""
    form = FeedForm(request.POST or None)
    if request.method == "POST":
        if not _is_superuser(request):
            raise PermissionDenied
        if form.is_valid():
            feed = form.save()
            audit.record(request.user, "add feed", str(feed), feed.url, request)
            messages.success(request, f"Added: {feed}.")
            return redirect("ops:feeds")
    context = {"feeds": NewsFeed.objects.all(), "form": form, "section": "feeds"}
    return render(request, "ops/feeds.html", context)


@superuser_post_required
def feed_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """Turn a feed on or off."""
    feed = get_object_or_404(NewsFeed, pk=pk)
    feed.enabled = not feed.enabled
    feed.save(update_fields=["enabled"])
    state = "on" if feed.enabled else "off"
    audit.record(request.user, f"turn {state} feed", str(feed), "", request)
    messages.success(request, f"{feed} is now {state}.")
    return redirect("ops:feeds")


@superuser_post_required
def feed_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a feed. Its articles stay."""
    feed = get_object_or_404(NewsFeed, pk=pk)
    label = str(feed)
    feed.delete()
    audit.record(request.user, "delete feed", label, feed.url, request)
    messages.success(request, f"{label} is deleted.")
    return redirect("ops:feeds")


# Instruments


@staff_required
def instrument_list(request: HttpRequest) -> HttpResponse:
    """The instruments with their weights. A superuser can change them and add new ones."""
    add_form = InstrumentForm(prefix="new")
    if request.method == "POST":
        if not _is_superuser(request):
            raise PermissionDenied
        add_form = InstrumentForm(request.POST, prefix="new")
        if add_form.is_valid():
            instrument = add_form.save()
            audit.record(request.user, "add instrument", str(instrument), "", request)
            messages.success(request, f"Added: {instrument}.")
            return redirect("ops:instruments")
    rows = [
        {"instrument": row, "form": InstrumentForm(instance=row, prefix=f"i{row.pk}")}
        for row in Instrument.objects.all()
    ]
    cues = list(Instrument.objects.filter(kind=Instrument.Kind.CUE, enabled=True))
    context = {
        "rows": rows,
        "add_form": add_form,
        "weight_total": round(sum(abs(c.weight) for c in cues), 4),
        "section": "instruments",
    }
    return render(request, "ops/instruments.html", context)


@superuser_post_required
def instrument_save(request: HttpRequest, pk: int) -> HttpResponse:
    """Save one instrument."""
    row = get_object_or_404(Instrument, pk=pk)
    form = InstrumentForm(request.POST, instance=row, prefix=f"i{pk}")
    if form.is_valid():
        before = f"weight {row.weight}, scale {row.scale}, enabled {row.enabled}"
        saved = form.save()
        after = f"weight {saved.weight}, scale {saved.scale}, enabled {saved.enabled}"
        audit.record(request.user, "change instrument", str(saved), f"{before} -> {after}", request)
        messages.success(request, f"Saved: {saved}.")
    else:
        errors = "; ".join(str(e) for errs in form.errors.values() for e in errs)
        messages.error(request, f"Not saved ({row}): {errors}")
    return redirect("ops:instruments")


@superuser_post_required
def instrument_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete an instrument. The target index cannot be deleted. Its old quotes stay."""
    row = get_object_or_404(Instrument, pk=pk)
    if row.kind == Instrument.Kind.TARGET:
        messages.error(request, "The target index cannot be deleted.")
        return redirect("ops:instruments")
    label = str(row)
    row.delete()
    audit.record(request.user, "delete instrument", label, "", request)
    messages.success(request, f"{label} is deleted.")
    return redirect("ops:instruments")
