"""Write the Python reference pages (MDX) from the inventory."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from . import checks, docstrings
from .inventory import Group, Member, Module, Param, Symbol

ADMONITIONS = {"note": "note", "notes": "note", "warning": "warning", "warnings": "warning"}


@dataclass(frozen=True)
class Context:
    """Where the source lives. It is used to make links to the code."""

    repo: str = "https://github.com/ananthunalloor/kashengine"
    ref: str = "main"

    def source_url(self, path: str, line: int | None = None) -> str:
        """Return the link to a file, or to a line of a file."""
        url = f"{self.repo}/blob/{self.ref}/{path}"
        return f"{url}#L{line}" if line else url


def module_slug(module: Module) -> str:
    """Return the file name (without extension) of a module page."""
    return module.short_name.replace(".", "-")


def module_url(module: Module) -> str:
    """Return the page path of a module, from the Python reference root."""
    return f"{module.group}/{module_slug(module)}"


def _front_matter(title: str, label: str, description: str = "") -> list[str]:
    lines = ["---", f"title: {title}", f"sidebar_label: {label}"]
    if description:
        lines.append("description: " + _yaml_quote(description))
    lines += ["toc_max_heading_level: 3", "---", ""]
    return lines


def _yaml_quote(text: str) -> str:
    return '"' + " ".join(text.split()).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _heading(symbol: Symbol) -> str:
    depth = min(symbol.qualified_name.count(".") + 2, 4)
    return "#" * depth


def _anchor(symbol: Symbol) -> str:
    return "{#" + symbol.qualified_name + "}"


def _signature_block(symbol: Symbol) -> list[str]:
    lines = ["```python", *(f"@{item}" for item in symbol.decorators)]
    if symbol.kind == "class":
        lines.append(symbol.signature + ":")
    else:
        lines.append(symbol.signature + ":")
    lines.append("```")
    return lines


def _params_table(symbol: Symbol, doc: docstrings.Docstring) -> list[str]:
    if not symbol.params:
        return []
    described = {
        entry.name.lstrip("*"): entry
        for section in doc.sections
        if section.name in docstrings.PARAM_SECTIONS
        for entry in section.entries
    }
    lines = [
        "**Parameters**",
        "",
        "| Name | Type | Default | Description |",
        "| --- | --- | --- | --- |",
    ]
    for param in symbol.params:
        entry = described.get(param.name.lstrip("*"))
        kind = param.annotation or (entry.type if entry else "")
        text = entry.text if entry else ""
        lines.append(
            f"| `{param.name}` | {docstrings.code_cell(kind)} | "
            f"{docstrings.code_cell(param.default)} | {docstrings.cell(text)} |"
        )
    lines.append("")
    return lines


def _extra_sections(symbol: Symbol, doc: docstrings.Docstring) -> list[str]:
    lines: list[str] = []
    for section in doc.sections:
        if section.name in docstrings.PARAM_SECTIONS:
            continue
        if section.name in {"returns", "return", "yields"}:
            label = "Yields" if section.name == "yields" else "Returns"
            kind = f" `{symbol.returns}`" if symbol.returns else ""
            lines += [f"**{label}**{kind}", "", docstrings.prose(section.text), ""]
        elif section.kind == "raises":
            lines += ["**Raises**", ""]
            for entry in section.entries:
                text = docstrings.cell(entry.text)
                lines.append(f"- `{entry.name}`" + (f": {text}" if text else ""))
            lines.append("")
        elif section.kind == "code":
            lines += [f"**{section.title}**", "", docstrings.code_block(section.text), ""]
        elif section.name in ADMONITIONS:
            lines += [f":::{ADMONITIONS[section.name]}", docstrings.prose(section.text), ":::", ""]
        elif section.kind == "params":
            lines += [f"**{section.title}**", ""]
            for entry in section.entries:
                kind = f" (`{entry.type}`)" if entry.type else ""
                lines.append(f"- `{entry.name}`{kind}: {docstrings.cell(entry.text)}")
            lines.append("")
        else:
            lines += [f"**{section.title}**", "", docstrings.prose(section.text), ""]
    return lines


def _members_table(symbol: Symbol) -> list[str]:
    if not symbol.members:
        return []
    is_field = any(member.kind != "member" for member in symbol.members)
    if is_field:
        header = ["**Fields**", "", "| Field | Type | Options |", "| --- | --- | --- |"]
        rows = [
            f"| `{m.name}` | `{m.kind}` | {docstrings.code_cell(m.value)} |" for m in symbol.members
        ]
    else:
        header = ["**Members**", "", "| Name | Value |", "| --- | --- |"]
        rows = [f"| `{m.name}` | {docstrings.code_cell(m.value)} |" for m in symbol.members]
    return [*header, *rows, ""]


def render_symbol(symbol: Symbol, module: Module, ctx: Context) -> str:
    """Return the MDX of one class, method or function."""
    doc = docstrings.parse(symbol.docstring) if symbol.docstring.strip() else docstrings.Docstring()
    label = f"`{symbol.name}`" if "." not in symbol.qualified_name else f"`{symbol.qualified_name}`"
    lines = [f"{_heading(symbol)} {label} {_anchor(symbol)}", ""]
    lines += _signature_block(symbol)
    lines.append("")
    if not symbol.docstring.strip():
        lines += [":::caution", "This definition has no docstring yet.", ":::", ""]
    else:
        lines += [docstrings.escape(doc.summary), ""]
        if doc.description:
            lines += [docstrings.prose(doc.description), ""]
    if symbol.kind != "class":
        lines += _params_table(symbol, doc)
    lines += _members_table(symbol)
    lines += _extra_sections(symbol, doc)
    url = ctx.source_url(module.path, symbol.line)
    lines += [f"<small>Source: [`{module.path}:{symbol.line}`]({url})</small>", ""]
    return "\n".join(lines)


def _constants_table(constants: tuple[Member, ...]) -> list[str]:
    if not constants:
        return []
    lines = ["## Constants", "", "| Name | Type | Value |", "| --- | --- | --- |"]
    lines += [f"| `{c.name}` | `{c.kind}` | {docstrings.code_cell(c.value)} |" for c in constants]
    return [*lines, ""]


def render_module(module: Module, ctx: Context) -> str:
    """Return the MDX page of one module."""
    doc = docstrings.parse(module.docstring) if module.docstring else docstrings.Docstring()
    lines = _front_matter(module.name, module.short_name, doc.summary)
    lines += [f"# `{module.name}`", ""]
    lines += [
        "<small>"
        f"Source: [`{module.path}`]({ctx.source_url(module.path)}) · {module.lines} lines"
        "</small>",
        "",
    ]
    if module.parse_error:
        lines += [
            ":::danger",
            f"The generator could not parse this file: `{module.parse_error}`",
            ":::",
            "",
        ]
    if module.docstring:
        lines += [docstrings.escape(doc.summary), ""]
        if doc.description:
            lines += [docstrings.prose(doc.description), ""]
        lines += _extra_sections(Symbol("function", "", "", 0, 0, "", ""), doc)
    else:
        lines += [":::caution", "This module has no docstring yet.", ":::", ""]
    lines += _constants_table(module.constants)
    shown = [
        s for s in module.symbols if not s.is_nested and "Meta" not in s.qualified_name.split(".")
    ]
    if not shown:
        lines += ["This module defines no classes or functions.", ""]
    for symbol in shown:
        lines.append(render_symbol(symbol, module, ctx))
    return "\n".join(lines).rstrip() + "\n"


def _counts(modules: list[Module]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for module in modules:
        for finding in checks.findings([module]):
            counter[finding.status] += 1
        counter["total"] += sum(1 for s in module.symbols if not checks.is_exempt(s)) + int(
            module.has_code
        )
    return counter


def render_group(group: Group) -> str:
    """Return the index page of one app."""
    lines = _front_matter(group.name, group.name, f"Python modules of the {group.name} package.")
    lines += [
        f"# `{group.name}`",
        "",
        "| Module | Summary | Definitions | Docstring check |",
        "| --- | --- | ---: | --- |",
    ]
    for module in group.modules:
        if not module.has_code:
            continue
        summary = docstrings.parse(module.docstring).summary if module.docstring else ""
        bad = len(checks.findings([module]))
        state = "Complete" if bad == 0 else f"{bad} to fix"
        lines.append(
            f"| [`{module.short_name}`](./{module_slug(module)}.md) | {docstrings.cell(summary)} | "
            f"{len(module.symbols)} | {state} |"
        )
    return "\n".join(lines) + "\n"


def render_overview(modules: list[Module], groups: list[Group]) -> str:
    """Return the landing page of the Python reference."""
    counts = _counts(modules)
    total = counts["total"]
    done = total - counts["Incomplete"] - counts["Missing"]
    lines = _front_matter(
        "Python reference",
        "Python reference",
        "Classes, methods and functions of the Kash Engine source code.",
    )
    lines += [
        "# Python reference",
        "",
        "This reference lists every module, class, method and function in the production source code "
        "(`apps/`, `config/` and `manage.py`). Tests and migrations are not included. "
        "The pages are generated from the source docstrings. The code is read with Python `ast`, "
        "never run. To change a page, change the docstring in the source file.",
        "",
        f"**Modules:** {len(modules)} · **Definitions checked:** {total} · "
        f"**Complete:** {done} · **Incomplete:** {counts['Incomplete']} · **Missing:** {counts['Missing']}",
        "",
        "## Packages",
        "",
        "| Package | Modules | Definitions | To fix |",
        "| --- | ---: | ---: | ---: |",
    ]
    for group in groups:
        items = list(group.modules)
        bad = len(checks.findings(items))
        symbols = sum(len(m.symbols) for m in items)
        lines.append(
            f"| [`{group.name}`](./{group.name}/index.md) | {len(items)} | {symbols} | {bad} |"
        )
    lines += [
        "",
        "## Docstring contract",
        "",
        "The [docstring standard](../../../development/docstring-standard.md) defines what each "
        "docstring must contain. `npm run reference:check` fails when a definition does not meet it. "
        "The [coverage report](./coverage.md) lists what is left to do.",
        "",
    ]
    return "\n".join(lines)


def render_coverage(modules: list[Module], ctx: Context) -> str:
    """Return the page that lists all docstring problems."""
    found = checks.findings(modules)
    lines = _front_matter(
        "Docstring coverage",
        "Docstring coverage",
        "Definitions that do not meet the docstring contract.",
    )
    lines += ["# Docstring coverage", ""]
    if not found:
        lines += ["Every definition meets the docstring contract.", ""]
        return "\n".join(lines)
    lines += [
        f"{len(found)} definitions do not meet the contract.",
        "",
        "| Definition | Status | To fix |",
        "| --- | --- | --- |",
    ]
    for item in found:
        link = f"[`{item.path}:{item.line}`]({ctx.source_url(item.path, item.line)})"
        lines.append(
            f"| `{item.name}` ({link}) | {item.status} | {docstrings.cell('; '.join(item.problems))} |"
        )
    return "\n".join(lines) + "\n"


def render_param_table(params: tuple[Param, ...]) -> str:
    """Return a Markdown table of parameters (used by the CLI and task pages)."""
    lines = ["| Name | Type | Default |", "| --- | --- | --- |"]
    lines += [
        f"| `{p.name}` | {docstrings.code_cell(p.annotation)} | {docstrings.code_cell(p.default)} |"
        for p in params
    ]
    return "\n".join(lines)
