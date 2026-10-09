"""The log reader."""

import pytest

from apps.ops import logs

BOT_TOKEN = "123456789:AAEhBP0av28dTq9XYZ-abcdefghijklmnopqr"

SAMPLE = f"""\
2026-10-07 07:00:01,100 INFO apps.news.tasks: Fetched 12 articles
2026-10-07 07:00:02,200 WARNING apps.llm.client: Model is slow
2026-10-07 07:00:03,300 ERROR apps.delivery.telegram: Send failed
Traceback (most recent call last):
  File "x.py", line 1, in <module>
ValueError: boom
2026-10-07 07:00:04,400 INFO httpx: POST https://api.telegram.org/bot{BOT_TOKEN}/sendMessage
"""


@pytest.fixture
def log_file(tmp_path):
    path = tmp_path / "app.log"
    path.write_text(SAMPLE)
    return path


def test_a_traceback_belongs_to_its_record():
    entries = logs.parse(list(SAMPLE.splitlines()))

    assert len(entries) == 4
    assert entries[2].level == "ERROR"
    assert "ValueError: boom" in entries[2].message
    assert entries[2].message.startswith("Send failed\nTraceback")


def test_the_newest_entry_is_first(log_file):
    view = logs.query(path=log_file)

    assert view.exists
    assert view.matched == 4
    assert view.entries[0].time.endswith("07:00:04,400")


def test_the_level_is_a_minimum_level(log_file):
    view = logs.query(level="warning", path=log_file)

    assert [e.level for e in view.entries] == ["ERROR", "WARNING"]


def test_filters_by_logger_and_text(log_file):
    assert [e.logger for e in logs.query(logger_name="NEWS", path=log_file).entries] == [
        "apps.news.tasks"
    ]
    assert logs.query(text="slow", path=log_file).matched == 1
    assert logs.query(text="no such text", path=log_file).matched == 0


def test_the_limit_cuts_the_list_but_not_the_count(log_file):
    view = logs.query(limit=1, path=log_file)

    assert len(view.entries) == 1
    assert view.matched == 4


def test_a_bot_token_is_never_shown(log_file):
    view = logs.query(path=log_file)

    shown = "\n".join(e.message for e in view.entries)
    assert BOT_TOKEN not in shown
    assert "bot<hidden>" in shown


@pytest.mark.parametrize(
    "text",
    [
        "login with password=hunter2 failed",
        "using api_key: sk-abc123",
        "Authorization: Bearer abcdef.ghijk",
        "cookie sessionid=abc123def",
        "csrftoken=zzz",
    ],
)
def test_other_secrets_are_hidden(text):
    cleaned = logs.redact(text)

    assert "<hidden>" in cleaned
    for secret in ("hunter2", "sk-abc123", "abcdef.ghijk", "abc123def", "zzz"):
        assert secret not in cleaned


def test_a_missing_file_is_not_an_error(tmp_path):
    view = logs.query(path=tmp_path / "none.log")

    assert not view.exists
    assert view.entries == []


def test_only_the_end_of_a_big_file_is_read(tmp_path, settings):
    settings.OPS_LOG_TAIL_BYTES = 200
    path = tmp_path / "big.log"
    path.write_text(
        "".join(
            f"2026-10-07 07:00:{n % 60:02d},000 INFO a.b: line number {n}\n" for n in range(100)
        )
    )

    view = logs.query(path=path, limit=1000)

    assert view.matched < 10
    assert view.entries[0].message == "line number 99"
    assert all(e.time for e in view.entries)  # The cut first line is dropped.


@pytest.mark.parametrize(
    ("value", "expected"),
    [("50", 50), (None, 200), ("", 200), ("abc", 200), ("0", 1), ("-5", 1), ("999999", 1000)],
)
def test_the_limit_is_always_safe(value, expected):
    assert logs.clean_limit(value) == expected


def test_the_level_name_is_checked():
    assert logs.clean_level(" error ") == "ERROR"
    assert logs.clean_level("nonsense") == ""
