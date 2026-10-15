"""Parse Google-style docstrings and turn them into safe MDX text.

The parser is small on purpose. It understands the sections that the project docstring
standard uses (`Args`, `Returns`, `Raises`, `Example`, ...) and keeps all other text as it is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SECTION_RE = re.compile(r"^([A-Z][A-Za-z]*(?: [A-Za-z]+){0,2}):\s*$")
ENTRY_RE = re.compile(r"^(\*{0,2}[A-Za-z_][\w.]*)(?:\s*\(([^)]*)\))?\s*:\s?(.*)$")

#: Section name (lower case) -> (kind, title shown on the page).
SECTION_KINDS: dict[str, tuple[str, str]] = {
    "args": ("params", "Parameters"),
    "arguments": ("params", "Parameters"),
    "parameters": ("params", "Parameters"),
    "keyword args": ("params", "Keyword parameters"),
    "keyword arguments": ("params", "Keyword parameters"),
    "other parameters": ("params", "Other parameters"),
    "attributes": ("params", "Attributes"),
    "returns": ("text", "Returns"),
    "return": ("text", "Returns"),
    "yields": ("text", "Yields"),
    "raises": ("raises", "Raises"),
    "example": ("code", "Example"),
    "examples": ("code", "Examples"),
    "note": ("text", "Note"),
    "notes": ("text", "Notes"),
    "warning": ("text", "Warning"),
    "warnings": ("text", "Warning"),
    "see also": ("text", "See also"),
    "todo": ("text", "To do"),
}
PARAM_SECTIONS = {"args", "arguments", "parameters", "keyword args", "keyword arguments"}


@dataclass(frozen=True)
class Entry:
    """One `name (type): description` item of an Args or Raises section."""

    name: str
    type: str
    text: str


@dataclass(frozen=True)
class Section:
    """One named section of a docstring."""

    name: str  # The name as written, lower case.
    kind: str  # params, raises, text or code.
    title: str
    text: str  # Body text, dedented.
    entries: tuple[Entry, ...] = ()


@dataclass(frozen=True)
class Docstring:
    """A parsed docstring."""

    summary: str = ""
    description: str = ""
    sections: tuple[Section, ...] = field(default_factory=tuple)

    def section(self, *names: str) -> Section | None:
        """Return the first section that has one of the given names."""
        for item in self.sections:
            if item.name in names:
                return item
        return None

    @property
    def documented_params(self) -> set[str]:
        """The names in the Args section, without any leading stars."""
        found: set[str] = set()
        for item in self.sections:
            if item.name in PARAM_SECTIONS:
                found.update(entry.name.lstrip("*") for entry in item.entries)
        return found

    @property
    def raised(self) -> set[str]:
        """The exception names in the Raises section."""
        item = self.section("raises")
        return {entry.name for entry in item.entries} if item else set()


def _dedent(lines: list[str]) -> list[str]:
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    cut = min(indents) if indents else 0
    return [line[cut:] if line.strip() else "" for line in lines]


def _entries(lines: list[str]) -> tuple[Entry, ...]:
    """Split a params or raises body into entries."""
    lines = _dedent(lines)
    base = 0
    entries: list[Entry] = []
    current: tuple[str, str, list[str]] | None = None
    for line in lines:
        indent = len(line) - len(line.lstrip())
        match = ENTRY_RE.match(line) if indent == base and line.strip() else None
        if match:
            if current:
                entries.append(Entry(current[0], current[1], "\n".join(current[2]).strip()))
            current = (match.group(1), (match.group(2) or "").strip(), [match.group(3)])
        elif current is not None:
            current[2].append(line.strip() if line.strip() else "")
    if current:
        entries.append(Entry(current[0], current[1], "\n".join(current[2]).strip()))
    return tuple(entries)


def parse(text: str) -> Docstring:
    """Parse a cleaned docstring (as `ast.get_docstring(clean=True)` returns it)."""
    lines = text.strip("\n").splitlines()
    head: list[str] = []
    sections: list[Section] = []
    name: str | None = None
    body: list[str] = []

    def close() -> None:
        if name is None:
            return
        kind, title = SECTION_KINDS.get(name, ("text", name.capitalize()))
        entries = _entries(body) if kind in {"params", "raises"} else ()
        sections.append(Section(name, kind, title, "\n".join(_dedent(body)).strip(), entries))

    for index, line in enumerate(lines):
        match = SECTION_RE.match(line)
        if match and _starts_section(match.group(1), lines, index):
            close()
            name = match.group(1).lower()
            body = []
        elif name is None:
            head.append(line)
        else:
            body.append(line)
    close()

    paragraphs = "\n".join(head).strip().split("\n\n", 1)
    summary = " ".join(paragraphs[0].split())
    description = paragraphs[1].strip() if len(paragraphs) > 1 else ""
    return Docstring(summary, description, tuple(sections))


def _starts_section(title: str, lines: list[str], index: int) -> bool:
    """Tell a section header from a normal line that ends with a colon."""
    if title.lower() in SECTION_KINDS:
        return True
    following = next((line for line in lines[index + 1 :] if line.strip()), "")
    return bool(following) and following[:1].isspace() and index > 0


# ---------------------------------------------------------------------------------------
# MDX-safe text
# ---------------------------------------------------------------------------------------

_CODE_SPAN = re.compile(r"(`+)(.+?)\1", re.S)
_ESCAPES = {"<": "&lt;", ">": "&gt;", "{": "&#123;", "}": "&#125;"}


def escape(text: str) -> str:
    """Escape the characters that MDX reads as code, but keep inline code as it is."""
    out: list[str] = []
    last = 0
    for match in _CODE_SPAN.finditer(text):
        out.append(_escape_plain(text[last : match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(_escape_plain(text[last:]))
    return "".join(out)


def _escape_plain(text: str) -> str:
    return "".join(_ESCAPES.get(char, char) for char in text)


def cell(text: str) -> str:
    """Make text safe for one cell of a Markdown table."""
    return escape(" ".join(text.split())).replace("|", "\\|")


def code_cell(text: str) -> str:
    """Show a code value in a table cell."""
    value = " ".join(text.split())
    if not value:
        return ""
    return f"<code>{_escape_plain(value)}</code>".replace("|", "&#124;")


def prose(text: str) -> str:
    """Turn docstring text into MDX. Indented blocks become code, other text is escaped."""
    out: list[str] = []
    lines = text.splitlines()
    index = 0
    in_fence = False
    while index < len(lines):
        line = lines[index]
        if line.strip().startswith("```"):
            in_fence = not in_fence
            out.append(line.strip())
            index += 1
            continue
        if in_fence:
            out.append(line)
            index += 1
            continue
        previous_blank = not out or not out[-1].strip()
        if previous_blank and line.startswith("    ") and line.strip():
            block: list[str] = []
            while index < len(lines) and (
                lines[index].startswith("    ") or not lines[index].strip()
            ):
                block.append(lines[index])
                index += 1
            while block and not block[-1].strip():
                block.pop()
            out.extend(["```text", *_dedent(block), "```"])
            continue
        out.append(escape(line))
        index += 1
    return "\n".join(out).strip()


def code_block(text: str, language: str = "python") -> str:
    """Return text as a fenced code block, unless it already has a fence."""
    if "```" in text:
        return text
    return f"```{language}\n{text}\n```"
