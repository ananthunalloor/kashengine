"""Read the application log file for the log viewer.

The viewer reads the end of the file only (OPS_LOG_TAIL_BYTES), so a big file is not a problem.
It never writes. Secrets are hidden in every line that it shows.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LEVEL_RANK = {name: rank for rank, name in enumerate(LEVELS)}
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000
MAX_FILTER_CHARS = 100

LINE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) (?P<level>[A-Z]+) "
    r"(?P<logger>\S+): (?P<message>.*)$"
)

# A Telegram bot token is in the URL of each request. The other patterns are for safety.
SECRET_PATTERNS = (
    (re.compile(r"bot\d{5,}:[A-Za-z0-9_-]{20,}"), "bot<hidden>"),
    (
        re.compile(r"(?i)\b(token|secret|password|passwd|api[_-]?key)(\s*[=:]\s*)\S+"),
        r"\1\2<hidden>",
    ),
    (re.compile(r"(?i)\bBearer\s+\S+"), "Bearer <hidden>"),
    (re.compile(r"(?i)(sessionid|csrftoken)=\S+"), r"\1=<hidden>"),
)


@dataclass
class LogEntry:
    """One log record. A traceback is part of the message of its record."""

    time: str
    level: str
    logger: str
    message: str


@dataclass(frozen=True)
class LogView:
    """The answer to a log query."""

    entries: list[LogEntry]
    exists: bool
    size_bytes: int
    matched: int  # How many entries matched, before the limit.
    path: str


def redact(text: str) -> str:
    """Hide tokens, passwords, and session cookies in a line of text."""
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def read_tail_lines(path: Path, max_bytes: int) -> list[str]:
    """The last lines of a file. The cut line at the start of the chunk is dropped."""
    size = path.stat().st_size
    with path.open("rb") as handle:
        handle.seek(max(0, size - max_bytes))
        data = handle.read()
    lines = data.decode("utf-8", errors="replace").splitlines()
    if size > max_bytes and lines:
        lines = lines[1:]
    return lines


def parse(lines: list[str]) -> list[LogEntry]:
    """Group lines into records. A line that does not start a record continues the last one."""
    entries: list[LogEntry] = []
    for line in lines:
        match = LINE.match(line)
        if match:
            entries.append(LogEntry(**match.groupdict()))
        elif entries:
            entries[-1].message += "\n" + line
        elif line.strip():
            entries.append(LogEntry("", "", "", line))
    return entries


def clean_level(level: str) -> str:
    """A valid level name, or an empty text."""
    level = level.strip().upper()
    return level if level in LEVEL_RANK else ""


def clean_limit(value: str | int | None) -> int:
    """A safe number of entries."""
    try:
        number = int(value or DEFAULT_LIMIT)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return min(max(number, 1), MAX_LIMIT)


def query(
    level: str = "",
    logger_name: str = "",
    text: str = "",
    limit: int = DEFAULT_LIMIT,
    path: Path | None = None,
) -> LogView:
    """Return the newest log records that match. `level` is a minimum level."""
    path = path or Path(settings.LOG_FILE)
    if not path.is_file():
        return LogView([], exists=False, size_bytes=0, matched=0, path=str(path))

    entries = parse(read_tail_lines(path, settings.OPS_LOG_TAIL_BYTES))
    minimum = LEVEL_RANK.get(clean_level(level), -1)
    logger_name = logger_name.strip().lower()[:MAX_FILTER_CHARS]
    text = text.strip().lower()[:MAX_FILTER_CHARS]

    matched = []
    for entry in reversed(entries):  # The newest first.
        if minimum >= 0 and LEVEL_RANK.get(entry.level, -1) < minimum:
            continue
        if logger_name and logger_name not in entry.logger.lower():
            continue
        if text and text not in entry.message.lower():
            continue
        matched.append(entry)

    shown = [
        LogEntry(e.time, e.level, e.logger, redact(e.message))
        for e in matched[: clean_limit(limit)]
    ]
    return LogView(
        shown, exists=True, size_bytes=path.stat().st_size, matched=len(matched), path=str(path)
    )
