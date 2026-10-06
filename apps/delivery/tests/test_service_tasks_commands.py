"""Tests for the delivery service, the daily task, and the commands."""

# ruff: noqa: S105  (the test token is fake)
from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.delivery import service, tasks
from apps.delivery.management.commands import send_report as send_report_command
from apps.delivery.management.commands import telegram_check as telegram_check_command
from apps.delivery.models import DeliveryLog
from apps.delivery.service import DeliveryNotConfigured, deliver_report
from apps.delivery.telegram import TelegramError
from apps.reports.models import Report

pytestmark = pytest.mark.django_db

TOKEN = "123:SECRET"
DAY = date(2026, 10, 6)  # A Tuesday.
SATURDAY = date(2026, 10, 10)


class FakeTelegram:
    """A stand-in for TelegramClient. A chat in `fail` raises the error that it is mapped to."""

    def __init__(self, fail=None, token=TOKEN, chats=None):
        self.token = token
        self.fail = fail or {}
        self.sent: list[tuple[str, str]] = []
        self.chats = chats or []

    def send_message(self, chat_id, text):
        if chat_id in self.fail:
            raise self.fail[chat_id]
        self.sent.append((chat_id, text))
        return 1

    def get_me(self):
        return {"username": "kash_bot", "first_name": "Kash"}

    def get_chats(self):
        return self.chats

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


@pytest.fixture
def report():
    return Report.objects.create(date=DAY, text="The report text.", prediction="up", confidence=0.6)


# --- deliver_report ------------------------------------------------------------------------


def test_deliver_report_sends_to_each_chat_and_logs_it(report):
    telegram = FakeTelegram()

    result = deliver_report(report, ["1", "2"], client=telegram)

    assert result == {"sent": 2, "failed": 0, "skipped": 0, "errors": {}}
    assert telegram.sent == [("1", "The report text."), ("2", "The report text.")]
    logs = DeliveryLog.objects.order_by("recipient")
    assert [(log.recipient, log.status, log.channel, log.report) for log in logs] == [
        ("1", "sent", "telegram", report),
        ("2", "sent", "telegram", report),
    ]


def test_a_chat_that_got_the_report_is_skipped_unless_forced(report):
    deliver_report(report, ["1"], client=FakeTelegram())
    telegram = FakeTelegram()

    again = deliver_report(report, ["1", "2"], client=telegram)
    forced = deliver_report(report, ["1"], client=telegram, force=True)

    assert (again["sent"], again["skipped"]) == (1, 1)
    assert [chat for chat, _ in telegram.sent] == ["2", "1"]
    assert forced["sent"] == 1


def test_a_failed_chat_is_logged_without_the_token_and_does_not_stop_the_others(report):
    telegram = FakeTelegram(
        fail={"1": TelegramError(f"Telegram error 403: blocked (bot{TOKEN})", retryable=False)}
    )

    result = deliver_report(report, ["1", "2"], client=telegram)

    assert (result["sent"], result["failed"]) == (1, 1)
    assert TOKEN not in result["errors"]["1"]
    failed = DeliveryLog.objects.get(recipient="1")
    assert failed.status == "failed"
    assert "403" in failed.error
    assert TOKEN not in failed.error
    assert DeliveryLog.objects.get(recipient="2").status == "sent"


def test_a_failed_chat_gets_the_report_in_the_next_run(report):
    deliver_report(report, ["1"], client=FakeTelegram(fail={"1": TelegramError("down", True)}))
    telegram = FakeTelegram()

    result = deliver_report(report, ["1"], client=telegram)

    assert result["sent"] == 1  # A failed log does not count as "sent".
    assert telegram.sent == [("1", "The report text.")]


def test_the_error_text_is_cut(report):
    telegram = FakeTelegram(fail={"1": TelegramError("x" * 5000)})

    deliver_report(report, ["1"], client=telegram)

    assert len(DeliveryLog.objects.get().error) == 500


def test_deliver_report_needs_a_token_and_chat_ids(report, settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    settings.TELEGRAM_CHAT_IDS = ["1"]
    with pytest.raises(DeliveryNotConfigured, match="TOKEN"):
        deliver_report(report)

    settings.TELEGRAM_BOT_TOKEN = TOKEN
    settings.TELEGRAM_CHAT_IDS = [" ", ""]
    with pytest.raises(DeliveryNotConfigured, match="CHAT_IDS"):
        deliver_report(report)


def test_deliver_report_uses_the_settings_and_makes_its_own_client(report, settings, monkeypatch):
    settings.TELEGRAM_BOT_TOKEN = TOKEN
    settings.TELEGRAM_CHAT_IDS = [" 7 ", "8"]
    telegram = FakeTelegram()
    monkeypatch.setattr(service, "TelegramClient", lambda: telegram)

    result = deliver_report(report)

    assert result["sent"] == 2
    assert [chat for chat, _ in telegram.sent] == ["7", "8"]


# --- The task ------------------------------------------------------------------------------


def test_the_task_skips_the_weekend(monkeypatch):
    monkeypatch.setattr(tasks, "today_ist", lambda: SATURDAY)
    monkeypatch.setattr(tasks, "build_report", lambda day: pytest.fail("must not build"))

    assert "skipped" in tasks.send_daily_report()


def test_the_task_builds_and_sends(monkeypatch, report):
    monkeypatch.setattr(tasks, "today_ist", lambda: DAY)
    monkeypatch.setattr(tasks, "build_report", lambda day: (report, True))
    monkeypatch.setattr(
        tasks, "deliver_report", lambda r: {"sent": 1, "failed": 0, "skipped": 0, "errors": {}}
    )

    result = tasks.send_daily_report()

    assert result["date"] == "2026-10-06"
    assert result["built"] is True
    assert result["sent"] == 1


def test_the_task_still_builds_the_report_when_telegram_is_not_set(monkeypatch, report):
    monkeypatch.setattr(tasks, "today_ist", lambda: DAY)
    monkeypatch.setattr(tasks, "build_report", lambda day: (report, False))

    def not_configured(_report):
        raise DeliveryNotConfigured("TELEGRAM_BOT_TOKEN is not set.")

    monkeypatch.setattr(tasks, "deliver_report", not_configured)

    result = tasks.send_daily_report()

    assert result == {
        "date": "2026-10-06",
        "built": False,
        "not_sent": "TELEGRAM_BOT_TOKEN is not set.",
    }


def test_the_retry_run_does_not_send_twice(monkeypatch, settings):
    settings.TELEGRAM_BOT_TOKEN = TOKEN
    settings.TELEGRAM_CHAT_IDS = ["1", "2"]
    telegram = FakeTelegram(fail={"2": TelegramError("down", True)})
    monkeypatch.setattr(service, "TelegramClient", lambda: telegram)
    monkeypatch.setattr(tasks, "today_ist", lambda: DAY)

    first = tasks.send_daily_report()
    telegram.fail.clear()
    second = tasks.send_daily_report()

    assert (first["sent"], first["failed"]) == (1, 1)
    assert (second["sent"], second["skipped"], second["built"]) == (1, 1, False)
    assert Report.objects.count() == 1
    assert [chat for chat, _ in telegram.sent] == ["1", "2"]


# --- Commands ------------------------------------------------------------------------------


def test_build_report_command_shows_the_text(capsys):
    call_command("build_report", "--date", "2026-10-06")

    out = capsys.readouterr().out
    assert "--- Report 2026-10-06" in out
    assert "KASH ENGINE: DAILY REPORT, Tue 6 Oct 2026" in out
    assert Report.objects.get().date == DAY

    call_command("build_report", "--date", "2026-10-06")
    assert "exists already" in capsys.readouterr().out


def test_build_report_command_rejects_a_bad_date():
    with pytest.raises(CommandError, match="YYYY-MM-DD"):
        call_command("build_report", "--date", "6/10/2026")


def test_send_report_command_sends_and_reports(monkeypatch, capsys, settings):
    settings.TELEGRAM_CHAT_IDS = ["1"]
    sent = []
    monkeypatch.setattr(
        send_report_command,
        "deliver_report",
        lambda report, force=False: (
            sent.append(force) or {"sent": 1, "failed": 0, "skipped": 0, "errors": {}}
        ),
    )

    call_command("send_report", "--date", "2026-10-06", "--force")

    out = capsys.readouterr().out
    assert "Report 2026-10-06: built." in out
    assert "Telegram: 1 sent, 0 failed, 0 skipped." in out
    assert sent == [True]


def test_send_report_command_fails_loudly_when_a_chat_fails(monkeypatch, capsys):
    monkeypatch.setattr(
        send_report_command,
        "deliver_report",
        lambda report, force=False: {
            "sent": 0,
            "failed": 1,
            "skipped": 0,
            "errors": {"1": "Telegram error 400: chat not found"},
        },
    )

    with pytest.raises(CommandError, match="Run the command again"):
        call_command("send_report", "--date", "2026-10-06")

    assert "chat not found" in capsys.readouterr().out


def test_send_report_command_explains_a_missing_setting(settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    settings.TELEGRAM_CHAT_IDS = []

    with pytest.raises(CommandError, match="TELEGRAM_BOT_TOKEN"):
        call_command("send_report", "--date", "2026-10-06")


def test_send_report_command_rejects_a_bad_date():
    with pytest.raises(CommandError, match="YYYY-MM-DD"):
        call_command("send_report", "--date", "tomorrow")


def test_send_report_test_message(monkeypatch, capsys, settings):
    settings.TELEGRAM_CHAT_IDS = ["1", "2"]
    telegram = FakeTelegram()
    monkeypatch.setattr(send_report_command, "TelegramClient", lambda: telegram)

    call_command("send_report", "--test")

    assert [chat for chat, _ in telegram.sent] == ["1", "2"]
    assert "Test message sent to 2." in capsys.readouterr().out
    assert not Report.objects.exists()


def test_send_report_test_message_errors(monkeypatch, settings):
    settings.TELEGRAM_CHAT_IDS = []
    with pytest.raises(CommandError, match="TELEGRAM_CHAT_IDS is empty"):
        call_command("send_report", "--test")

    settings.TELEGRAM_CHAT_IDS = ["1"]
    monkeypatch.setattr(
        send_report_command,
        "TelegramClient",
        lambda: FakeTelegram(fail={"1": TelegramError("Telegram error 403: blocked")}),
    )
    with pytest.raises(CommandError, match="403"):
        call_command("send_report", "--test")


def test_telegram_check_shows_the_bot_and_the_chats(monkeypatch, capsys, settings):
    settings.TELEGRAM_BOT_TOKEN = TOKEN
    settings.TELEGRAM_CHAT_IDS = ["11"]
    chats = [
        {"id": 11, "type": "private", "name": "Ann Lee"},
        {"id": -100, "type": "group", "name": "Traders"},
    ]
    monkeypatch.setattr(telegram_check_command, "TelegramClient", lambda: FakeTelegram(chats=chats))

    call_command("telegram_check")

    out = capsys.readouterr().out
    assert "Bot: @kash_bot (Kash)" in out
    assert "TELEGRAM_CHAT_IDS: 11" in out
    assert "11  private  Ann Lee  (set)" in out
    assert "-100  group  Traders" in out
    assert TOKEN not in out


def test_telegram_check_tells_what_to_do_when_no_chat_wrote(monkeypatch, capsys, settings):
    settings.TELEGRAM_BOT_TOKEN = TOKEN
    monkeypatch.setattr(telegram_check_command, "TelegramClient", lambda: FakeTelegram())

    call_command("telegram_check")

    assert "Send any message to your bot" in capsys.readouterr().out


def test_telegram_check_errors(monkeypatch, settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    with pytest.raises(CommandError, match="@BotFather"):
        call_command("telegram_check")

    settings.TELEGRAM_BOT_TOKEN = TOKEN

    class Broken(FakeTelegram):
        def get_me(self):
            raise TelegramError("Telegram error 401: Unauthorized")

    monkeypatch.setattr(telegram_check_command, "TelegramClient", lambda: Broken())
    with pytest.raises(CommandError, match="401"):
        call_command("telegram_check")
