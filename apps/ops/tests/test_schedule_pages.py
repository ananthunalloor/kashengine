"""The schedule: the functions, the pages, and the health checks that use it."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse
from django_celery_beat.models import PeriodicTask

from apps.ops import schedule
from apps.ops.defaults import DEFAULT_SCHEDULE
from apps.ops.models import AuditEvent

pytestmark = pytest.mark.django_db

TASK = "news.fetch_feeds"
IST = ZoneInfo("Asia/Kolkata")


def _form(**overrides):
    values = {
        "name": "my-entry",
        "task": TASK,
        "minute": "15",
        "hour": "9",
        "day_of_week": "*",
        "day_of_month": "*",
        "month": "*",
        "enabled": "on",
    }
    values.update(overrides)
    return {key: value for key, value in values.items() if value is not None}


def _pk(name: str) -> int:
    return PeriodicTask.objects.get(name=name).pk


# Functions


def test_the_default_schedule_is_in_the_database():
    names = set(PeriodicTask.objects.values_list("name", flat=True))

    for name, *_rest in DEFAULT_SCHEDULE:
        assert name in names


def test_parse_cron_accepts_a_good_schedule():
    cron = schedule.parse_cron("*/5", "9-17", "mon-fri", "*", "*")

    assert 5 in cron.minute


@pytest.mark.parametrize("bad", ["61", "abc", "*/0", "1-"])
def test_parse_cron_refuses_a_bad_minute(bad):
    with pytest.raises(ValueError, match="not valid"):
        schedule.parse_cron(bad, "*", "*", "*", "*")


def test_preview_gives_the_next_times_in_order():
    cron = schedule.parse_cron("0", "7", "*", "*", "*")
    now = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)

    times = schedule.preview(cron, now, count=3)

    assert len(times) == 3
    assert times == sorted(times)
    assert all(t > now for t in times)


def test_preview_gives_the_right_times_for_a_fixed_clock():
    cron = schedule.parse_cron("30", "7", "*", "*", "*")
    now = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)

    times = schedule.preview(cron, now, count=3)

    local = [t.astimezone(IST) for t in times]  # The schedule is in IST.
    assert [t.day for t in local] == [6, 7, 8]
    assert {(t.hour, t.minute) for t in local} == {(7, 30)}


def test_next_after_reads_the_cron_fields_in_ist():
    cron = schedule.parse_cron("0", "*/6", "*", "*", "*")
    after = datetime(2026, 1, 5, 6, 0, tzinfo=UTC)  # 11:30 IST

    nxt = schedule.next_after(cron, after)

    assert nxt == datetime(2026, 1, 5, 12, 0, tzinfo=IST)


def test_a_morning_entry_is_due_at_its_ist_time():
    entry = next(e for e in schedule.entries() if e.name == "predict-market")  # 07:00 IST
    after = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)  # 05:30 IST

    assert schedule.next_after(entry.schedule, after) == datetime(2026, 1, 5, 7, 0, tzinfo=IST)


def test_overdue_by_uses_the_time_of_the_last_run():
    PeriodicTask.objects.filter(task="ops.prune").update(enabled=True)
    last = datetime(2026, 1, 5, 4, 0, tzinfo=UTC)  # The task is due daily at 03:40 IST.

    late = schedule.overdue_by("ops.prune", last, datetime(2026, 1, 8, 4, 0, tzinfo=UTC))
    assert late is not None
    assert 2 < late.days + late.seconds / 86400 < 3  # Due on 6 Jan, so about 2.x days late.

    assert schedule.overdue_by("ops.prune", last, datetime(2026, 1, 5, 20, 0, tzinfo=UTC)) is None


def test_times_on_follows_the_weekdays():
    monday, sunday = date(2026, 1, 5), date(2026, 1, 4)

    assert (7, 30) in schedule.times_on("delivery.send_daily_report", monday)
    assert schedule.times_on("delivery.send_daily_report", sunday) == []


def test_save_entry_adds_and_changes():
    row = schedule.save_entry(None, **_fields())
    assert row.crontab.hour == "9"

    schedule.save_entry(row.pk, **_fields(hour="10", enabled=False))
    row.refresh_from_db()

    assert row.crontab.hour == "10"
    assert row.enabled is False


def _fields(**overrides):
    fields = {
        "name": "my-entry",
        "task": TASK,
        "minute": "15",
        "hour": "9",
        "day_of_week": "*",
        "day_of_month": "*",
        "month": "*",
        "enabled": True,
    }
    fields.update(overrides)
    return fields


def test_save_entry_refuses_an_unknown_task():
    with pytest.raises(ValueError, match="cannot be scheduled"):
        schedule.save_entry(None, **_fields(task="os.system"))


def test_save_entry_refuses_a_duplicate_name():
    schedule.save_entry(None, **_fields())

    with pytest.raises(ValueError, match="Another entry has this name"):
        schedule.save_entry(None, **_fields())


def test_save_entry_refuses_a_bad_cron():
    with pytest.raises(ValueError, match="not valid"):
        schedule.save_entry(None, **_fields(minute="99"))


def test_a_disabled_entry_does_not_count():
    PeriodicTask.objects.filter(task="ops.prune").update(enabled=False)

    assert schedule.entries_for("ops.prune") == []
    assert schedule.next_run("ops.prune", datetime.now(UTC)) is None
    assert schedule.entries_for("ops.prune", enabled_only=False)


def test_reset_to_default_replaces_the_changes():
    PeriodicTask.objects.filter(task="ops.prune").delete()
    schedule.save_entry(None, **_fields(name="extra", task="ops.prune", hour="1"))

    count = schedule.reset_to_default()

    assert count == len(DEFAULT_SCHEDULE)
    assert [e.cron_text for e in schedule.entries_for("ops.prune")] == ["40 3 * * *"]


# Pages


@pytest.mark.parametrize("name", ["ops:schedule", "ops:schedule_add"])
def test_the_schedule_pages_follow_the_access_rules(
    client, member_client, staff_client, boss_client, offline, name
):
    url = reverse(name)

    assert client.get(url).status_code == 302
    assert member_client.get(url).status_code == 403
    assert staff_client.get(url).status_code == 200
    assert boss_client.get(url).status_code == 200


def test_the_list_shows_every_entry(boss_client, offline):
    page = boss_client.get(reverse("ops:schedule")).content.decode()

    for name, *_rest in DEFAULT_SCHEDULE:
        assert name in page


def test_the_buttons_are_for_a_superuser_only(boss_client, staff_client, offline):
    toggle = reverse("ops:schedule_toggle", args=[_pk("prune-ops-history")])

    assert toggle in boss_client.get(reverse("ops:schedule")).content.decode()
    assert toggle not in staff_client.get(reverse("ops:schedule")).content.decode()


def test_the_edit_page_shows_the_next_times(boss_client):
    page = boss_client.get(reverse("ops:schedule_edit", args=[_pk("prune-ops-history")]))

    assert page.status_code == 200
    assert len(page.context["upcoming"]) == 3


def test_an_unknown_entry_is_a_404(boss_client):
    assert boss_client.get(reverse("ops:schedule_edit", args=[999999])).status_code == 404


def test_a_superuser_adds_an_entry(boss_client):
    response = boss_client.post(reverse("ops:schedule_add"), _form())

    assert response.status_code == 302
    assert PeriodicTask.objects.filter(name="my-entry", task=TASK, enabled=True).exists()
    assert AuditEvent.objects.filter(action="add schedule", target="my-entry").exists()


def test_a_superuser_changes_an_entry(boss_client):
    pk = _pk("prune-ops-history")

    boss_client.post(
        reverse("ops:schedule_edit", args=[pk]),
        _form(name="prune-ops-history", task="ops.prune", hour="4", minute="0"),
    )

    assert [e.cron_text for e in schedule.entries_for("ops.prune")] == ["0 4 * * *"]
    assert AuditEvent.objects.filter(action="change schedule").exists()


def test_a_bad_cron_is_shown_and_nothing_is_saved(boss_client):
    response = boss_client.post(reverse("ops:schedule_add"), _form(minute="99"))

    assert response.status_code == 200
    assert "not valid" in response.content.decode()
    assert not PeriodicTask.objects.filter(name="my-entry").exists()


def test_a_task_that_is_not_in_the_list_is_refused(boss_client):
    response = boss_client.post(reverse("ops:schedule_add"), _form(task="os.system"))

    assert response.status_code == 200
    assert not PeriodicTask.objects.filter(name="my-entry").exists()


def test_a_staff_user_cannot_change_the_schedule(staff_client):
    assert staff_client.post(reverse("ops:schedule_add"), _form()).status_code == 403
    pk = _pk("prune-ops-history")
    for name in ("schedule_toggle", "schedule_delete"):
        assert staff_client.post(reverse(f"ops:{name}", args=[pk])).status_code == 403
    assert staff_client.post(reverse("ops:schedule_reset"), {"confirm": "yes"}).status_code == 403
    assert PeriodicTask.objects.filter(name="prune-ops-history", enabled=True).exists()


def test_the_buttons_need_a_post(boss_client):
    pk = _pk("prune-ops-history")

    assert boss_client.get(reverse("ops:schedule_toggle", args=[pk])).status_code == 405
    assert boss_client.get(reverse("ops:schedule_delete", args=[pk])).status_code == 405


def test_toggle_turns_an_entry_off_and_on(boss_client):
    pk = _pk("prune-ops-history")
    url = reverse("ops:schedule_toggle", args=[pk])

    boss_client.post(url)
    assert PeriodicTask.objects.get(pk=pk).enabled is False
    boss_client.post(url)
    assert PeriodicTask.objects.get(pk=pk).enabled is True
    assert AuditEvent.objects.filter(action__startswith="turn").count() == 2


def test_delete_removes_an_entry(boss_client):
    pk = _pk("prune-ops-history")

    boss_client.post(reverse("ops:schedule_delete", args=[pk]))

    assert not PeriodicTask.objects.filter(pk=pk).exists()
    assert AuditEvent.objects.filter(action="delete schedule").exists()


def test_reset_needs_the_confirm_box(boss_client):
    PeriodicTask.objects.filter(name="prune-ops-history").delete()

    boss_client.post(reverse("ops:schedule_reset"))
    assert not PeriodicTask.objects.filter(name="prune-ops-history").exists()

    boss_client.post(reverse("ops:schedule_reset"), {"confirm": "yes"})
    assert PeriodicTask.objects.filter(name="prune-ops-history").exists()
    assert AuditEvent.objects.filter(action="reset schedule").exists()


# Health checks follow the schedule


def test_the_prediction_check_is_skipped_when_the_task_is_not_scheduled(monkeypatch):
    from apps.ops import health  # noqa: PLC0415

    monkeypatch.setattr(health, "is_trading_day", lambda _day: True)
    PeriodicTask.objects.filter(task="markets.predict").delete()

    check = health.check_prediction()

    assert check.status == health.SKIP


def test_the_prediction_check_waits_for_a_late_schedule(monkeypatch):
    from apps.ops import health  # noqa: PLC0415

    monkeypatch.setattr(health, "is_trading_day", lambda _day: True)
    monkeypatch.setattr(health, "_late", lambda _task, _grace: False)

    assert health.check_prediction().status == health.OK


def test_the_prediction_check_fails_when_the_schedule_time_has_passed(monkeypatch):
    from apps.ops import health  # noqa: PLC0415

    monkeypatch.setattr(health, "is_trading_day", lambda _day: True)
    monkeypatch.setattr(health, "_late", lambda _task, _grace: True)

    assert health.check_prediction().status != health.OK
