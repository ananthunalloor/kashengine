"""Write the system reference pages: settings, schedule, jobs, tasks, commands and routes.

Every fact on these pages comes from the source code, read with `ast`. No project code runs.
So the pages cannot drift from the code, and the generator cannot read a secret.
"""

from __future__ import annotations

import ast
import re
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import docstrings

if TYPE_CHECKING:
    from pathlib import Path

SECRET_WORDS = ("SECRET", "TOKEN", "PASSWORD", "KEY")
ENV_METHODS = {"bool", "int", "float", "list", "str", "url", "db"}


def _text(node: ast.AST | None) -> str:
    """Return the value of a literal node as text. Fall back to the source of the node."""
    if node is None:
        return ""
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        parts = _flatten_add(node)
        if len(parts) > 1:
            return "".join(_text(part) for part in parts)
        return ast.unparse(node)
    return value if isinstance(value, str) else repr(value)


def _flatten_add(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return [*_flatten_add(node.left), *_flatten_add(node.right)]
    return [node]


def _parse(path: Path) -> tuple[ast.Module, list[str]]:
    source = path.read_text(encoding="utf-8")
    return ast.parse(source), source.splitlines()


def _comment(lines: list[str], lineno: int) -> str:
    match = re.search(r"\s#\s?(.*)$", lines[lineno - 1])
    return match.group(1).strip() if match else ""


def _summary(doc: str | None) -> str:
    return docstrings.parse(doc.strip()).summary if doc and doc.strip() else ""


# ----------------------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------------------
@dataclass
class Variable:
    """One environment variable that a settings file reads."""

    name: str
    kind: str
    default: str
    comment: str
    file: str
    spec: dict[str, str] = field(default_factory=dict)


def read_variables(root: Path) -> list[Variable]:
    """Return the environment variables read in `config/settings/*.py`.

    Args:
        root: The repository root.

    Returns:
        The variables, in file and line order. Secret defaults are replaced by `(hidden)`.
    """
    found: list[Variable] = []
    for path in sorted((root / "config" / "settings").glob("*.py")):
        tree, lines = _parse(path)
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
            ):
                continue
            func = node.func
            is_env = (isinstance(func, ast.Name) and func.id == "env") or (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "env"
                and func.attr in ENV_METHODS
            )
            if not is_env or not isinstance(node.args[0].value, str):
                continue
            name = node.args[0].value
            default = next((kw.value for kw in node.keywords if kw.arg == "default"), None)
            kind = func.attr if isinstance(func, ast.Attribute) else "str"
            shown = "" if default is None else ast.unparse(default)
            has_text = (
                isinstance(default, ast.Constant)
                and isinstance(default.value, str)
                and bool(default.value)
            )
            if any(word in name for word in SECRET_WORDS) and has_text:
                shown = "(hidden)"
            found.append(
                Variable(name, kind, shown or "(required)", _comment(lines, node.lineno), path.name)
            )
    return found


def read_specs(root: Path) -> dict[str, dict[str, str]]:
    """Return the dashboard settings from `apps/siteconfig/registry.py`.

    Args:
        root: The repository root.

    Returns:
        A mapping from the setting key to its label, kind, group, help and limits.
    """
    tree, _lines = _parse(root / "apps" / "siteconfig" / "registry.py")
    kinds: dict[str, str] = {}
    groups: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Tuple):
            names = [t for t in node.targets if isinstance(t, ast.Tuple)]
            if names and len(names[0].elts) == len(node.value.elts):
                for name, value in zip(names[0].elts, node.value.elts, strict=True):
                    if isinstance(name, ast.Name) and isinstance(value, ast.Constant):
                        kinds[name.id] = str(value.value)
        is_groups = isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "GROUPS"
        if is_groups and node.value is not None:
            for item in ast.literal_eval(node.value):
                groups[item[0]] = item[1]
    specs: dict[str, dict[str, str]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Spec"):
            continue
        args = [*node.args]
        keys = ["key", "label", "kind", "group", "help", "minimum", "maximum"]
        data = {name: args[i] for i, name in enumerate(keys) if i < len(args)}
        data.update({kw.arg: kw.value for kw in node.keywords if kw.arg})
        key = _text(data["key"])
        kind = data["kind"]
        specs[key] = {
            "label": _text(data["label"]),
            "kind": kinds.get(kind.id, _text(kind)) if isinstance(kind, ast.Name) else _text(kind),
            "group": groups.get(_text(data["group"]), _text(data["group"])),
            "help": _text(data.get("help")),
            "minimum": _text(data.get("minimum")) if "minimum" in data else "",
            "maximum": _text(data.get("maximum")) if "maximum" in data else "",
        }
    return specs


def render_settings(variables: list[Variable], specs: dict[str, dict[str, str]]) -> str:
    """Return the settings page. It has one table for the dashboard settings and one for the rest."""
    by_name = {item.name: item for item in variables}
    lines = _front(
        "Settings and environment variables",
        "Settings",
        "Every setting and environment variable.",
        1,
    )
    lines += [
        "# Settings and environment variables",
        "",
        "A **dashboard setting** can be changed by a superuser on **Ops > Settings**. A saved value wins over "
        "the environment variable. It takes effect in a few seconds with no restart. "
        "A secret value is saved encrypted and is never shown again.",
        "",
        "An **environment variable** that is not a dashboard setting can change only when the process "
        "starts.",
        "",
        "## Dashboard settings",
        "",
        "| Key | Group | Type | Default | Limits | Description |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for key, spec in specs.items():
        var = by_name.get(key)
        default = "(secret)" if spec["kind"] == "secret" else (var.default if var else "see code")
        limits = " to ".join(x for x in (spec["minimum"], spec["maximum"]) if x)
        lines.append(
            f"| `{key}` | {docstrings.cell(spec['group'])} | {spec['kind']} | {docstrings.code_cell(default)} | "
            f"{limits} | {docstrings.cell(spec['label'] + '. ' + spec['help'])} |"
        )
    lines += [
        "",
        "## Other environment variables",
        "",
        "| Variable | Type | Default | File | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for var in variables:
        if var.name in specs:
            continue
        lines.append(
            f"| `{var.name}` | {var.kind} | {docstrings.code_cell(var.default)} | `{var.file}` | {docstrings.cell(var.comment)} |"
        )
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------------------
# Schedule and jobs
# ----------------------------------------------------------------------------------------
def render_schedule(root: Path) -> str:
    """Return the page of the default beat schedule (`apps/ops/defaults.py`)."""
    tree, _lines = _parse(root / "apps" / "ops" / "defaults.py")
    entries: list[tuple[str, ...]] = []
    for node in tree.body:
        is_schedule = (
            isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "DEFAULT_SCHEDULE"
        )
        if is_schedule and node.value is not None:
            entries = list(ast.literal_eval(node.value))
    lines = _front("Default schedule", "Schedule", "The first beat schedule. All times are IST.", 2)
    lines += [
        "# Default schedule",
        "",
        "The first migration saves this schedule in the database. After that, a superuser edits it on "
        "**Ops > Schedule**. **Reset to default** restores this list. All times are IST (Asia/Kolkata). "
        "The fields are the five fields of a cron line.",
        "",
        "| Name | Task | Minute | Hour | Day of week |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [f"| `{n}` | `{t}` | `{m}` | `{h}` | `{d}` |" for n, t, m, h, d in entries]
    return "\n".join(lines) + "\n"


def render_jobs(root: Path) -> str:
    """Return the page of the jobs that a superuser can start (`apps/ops/jobs.py`)."""
    tree, _lines = _parse(root / "apps" / "ops" / "jobs.py")
    rows: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Job":
            names = ["key", "label", "description", "kind", "target"]
            data = {n: node.args[i] for i, n in enumerate(names) if i < len(node.args)}
            data.update({kw.arg: kw.value for kw in node.keywords if kw.arg})
            kind = data["kind"]
            rows.append(
                {
                    "key": _text(data["key"]),
                    "label": _text(data["label"]),
                    "description": _text(data["description"]),
                    "kind": "task" if getattr(kind, "id", "") == "TASK" else "command",
                    "target": _text(data["target"]),
                    "group": _text(data.get("group")) or "Other",
                    "args": " ".join(_text(a) for a in getattr(data.get("args"), "elts", [])),
                    "confirm": "yes" if data.get("confirm") else "",
                }
            )
    lines = _front("Jobs", "Jobs", "The jobs on Ops > Jobs.", 3)
    lines += [
        "# Jobs",
        "",
        "A superuser can start these jobs on **Ops > Jobs**. A task job sends the Celery task to the worker. "
        "A command job runs a management command in the worker. Each start makes a task run row with "
        "the user who started it. A job that has a confirm text asks for a confirmation first.",
        "",
        "| Group | Key | Label | Type | Target | Confirm | Description |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        target = row["target"] + (f" {row['args']}" if row["args"] else "")
        lines.append(
            f"| {row['group']} | `{row['key']}` | {docstrings.cell(row['label'])} | {row['kind']} | "
            f"`{target}` | {row['confirm']} | {docstrings.cell(row['description'])} |"
        )
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------------------
# Tasks, commands, routes
# ----------------------------------------------------------------------------------------
def render_tasks(root: Path) -> str:
    """Return the page of the Celery tasks. It reads `@shared_task` decorators."""
    rows: list[tuple[str, str, str, str]] = []
    for path in sorted((root / "apps").glob("*/tasks.py")):
        tree, _lines = _parse(path)
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for deco in node.decorator_list:
                if isinstance(deco, ast.Call) and getattr(deco.func, "id", "") == "shared_task":
                    opts = {kw.arg: _text(kw.value) for kw in deco.keywords if kw.arg}
                    limit = opts.get("soft_time_limit", "")
                    rows.append(
                        (
                            opts.get("name", node.name),
                            f"{path.parent.name}.{node.name}",
                            limit,
                            _summary(ast.get_docstring(node)),
                        )
                    )
    lines = _front("Celery tasks", "Tasks", "Every Celery task and its time limit.", 4)
    lines += [
        "# Celery tasks",
        "",
        "The name is the registered Celery name. Use it in the schedule. The soft time limit is in seconds. "
        "A task that goes over it gets `SoftTimeLimitExceeded`.",
        "",
        "| Task name | Function | Soft limit (s) | Summary |",
        "| --- | --- | ---: | --- |",
    ]
    lines += [
        f"| `{n}` | `{f}` | {limit or ''} | {docstrings.cell(s)} |"
        for n, f, limit, s in sorted(rows)
    ]
    return "\n".join(lines) + "\n"


def render_commands(root: Path) -> str:
    """Return the page of the management commands and their options."""
    lines = _front("Management commands", "Commands", "Every manage.py command of the project.", 5)
    lines += [
        "# Management commands",
        "",
        "Run a command with `python manage.py <name>`. In Docker, run it in the `web` service.",
        "",
    ]
    for path in sorted((root / "apps").glob("*/management/commands/*.py")):
        if path.name.startswith("_"):
            continue
        tree, _src = _parse(path)
        cls = next(
            (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Command"), None
        )
        if cls is None:
            continue
        help_text = ""
        for node in cls.body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "help":
                help_text = _text(node.value)
        lines += [
            f"## `{path.stem}`",
            "",
            f"App: `{path.parent.parent.parent.name}`. {docstrings.escape(help_text or _summary(ast.get_docstring(cls)))}",
            "",
        ]
        options = []
        for call in ast.walk(cls):
            if isinstance(call, ast.Call) and getattr(call.func, "attr", "") == "add_argument":
                flags = ", ".join(_text(a) for a in call.args)
                opts = {kw.arg: kw.value for kw in call.keywords if kw.arg}
                kind = getattr(opts.get("type"), "id", "") or (
                    "flag" if _text(opts.get("action")) == "store_true" else "str"
                )
                default = _text(opts["default"]) if "default" in opts else ""
                options.append((flags, kind, default, _text(opts.get("help"))))
        if options:
            lines += ["| Option | Type | Default | Description |", "| --- | --- | --- | --- |"]
            lines += [
                f"| `{f}` | {k} | {docstrings.code_cell(d)} | {docstrings.cell(h)} |"
                for f, k, d, h in options
            ]
            lines.append("")
    return "\n".join(lines) + "\n"


def _url_rows(path: Path, prefix: str) -> list[tuple[str, str, str]]:
    tree, _lines = _parse(path)
    rows = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", "") in {"path", "re_path"}
            and node.args
        ):
            route = _text(node.args[0])
            target = ast.unparse(node.args[1]) if len(node.args) > 1 else ""
            name = next((_text(kw.value) for kw in node.keywords if kw.arg == "name"), "")
            if target.startswith("include("):
                continue
            rows.append((f"/{prefix}{route}", target, name))
    return rows


def render_routes(root: Path) -> str:
    """Return the page of the web routes. It reads `urls.py` files and the mount points."""
    tree, _lines = _parse(root / "config" / "urls.py")
    mounts: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", "") == "path"
            and len(node.args) > 1
        ):
            inner = node.args[1]
            if isinstance(inner, ast.Call) and getattr(inner.func, "id", "") == "include":
                mounts.append((_text(node.args[0]), _text(inner.args[0])))
    lines = _front("URL routes", "Routes", "Every URL of the web app and the API.", 6)
    lines += [
        "# URL routes",
        "",
        "The ninja routes of the API are in the [HTTP API reference](../http/index.md).",
        "",
    ]
    for prefix, module in mounts:
        target = root / (module.replace(".", "/") + ".py")
        if target.exists():
            lines += [
                f"## `/{prefix}` from `{module}`",
                "",
                "| URL | View | Name |",
                "| --- | --- | --- |",
            ]
            lines += [f"| `{u}` | `{v}` | `{n}` |" for u, v, n in _url_rows(target, prefix)]
            lines.append("")
    lines += ["## Root routes", "", "| URL | View | Name |", "| --- | --- | --- |"]
    lines += [
        f"| `{u}` | `{v}` | `{n}` |" for u, v, n in _url_rows(root / "config" / "urls.py", "")
    ]
    return "\n".join(lines) + "\n"


def _front(title: str, label: str, description: str, position: int) -> list[str]:
    return [
        "---",
        f"title: {title}",
        f"sidebar_label: {label}",
        f'description: "{description}"',
        f"sidebar_position: {position}",
        "---",
        "",
    ]


def write(root: Path, target: Path) -> None:
    """Write the system reference pages.

    Args:
        root: The repository root.
        target: The output folder. The function empties it first.
    """
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    pages = {
        "settings.md": render_settings(read_variables(root), read_specs(root)),
        "schedule.md": render_schedule(root),
        "jobs.md": render_jobs(root),
        "tasks.md": render_tasks(root),
        "commands.md": render_commands(root),
        "routes.md": render_routes(root),
    }
    for name, text in pages.items():
        (target / name).write_text(text, encoding="utf-8")
    (target / "_category_.json").write_text(
        '{"label": "System reference", "position": 2}\n', encoding="utf-8"
    )
