#!/usr/bin/env python3
"""Generate a source-level Python API reference for the Docusaurus site.

The generator uses Python's AST parser. It does not import project modules, so it
cannot start Django, connect to services, run task registration code, or read
runtime secrets while documenting the source tree.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = ("apps", "config", "manage.py")
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "docs" / "reference" / "generated"
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "migrations",
    "node_modules",
    "staticfiles",
    "tests",
}
SECTION_NAMES = {
    "args": "Parameters",
    "arguments": "Parameters",
    "parameters": "Parameters",
    "returns": "Returns",
    "yields": "Yields",
    "raises": "Raises",
    "warns": "Warnings",
    "warnings": "Warnings",
    "attributes": "Attributes",
    "examples": "Examples",
    "example": "Example",
    "notes": "Notes",
    "note": "Notes",
    "side effects": "Side effects",
    "concurrency": "Concurrency",
    "transaction": "Transaction behavior",
    "retry": "Retry behavior",
    "security": "Security",
    "see also": "See also",
}
SECTION_RE = re.compile(r"^\s*([A-Za-z][A-Za-z ]*):\s*$")
PARAM_RE = re.compile(r"^\s{0,12}([*]{0,2}[A-Za-z_]\w*)(?:\s*\([^)]*\))?:\s*(.*)$")


@dataclass(frozen=True)
class Symbol:
    """A class or callable found in one Python module."""

    kind: str
    qualified_name: str
    name: str
    line: int
    end_line: int
    signature: str
    docstring: str
    decorators: tuple[str, ...]
    parameters: tuple[str, ...] = ()
    returns_annotation: str | None = None
    has_raise: bool = False
    has_yield: bool = False

    @property
    def status(self) -> str:
        """Return the documentation completeness category for this symbol."""
        if self.kind == "class":
            if not self.docstring.strip():
                return "Missing"
            if len(self.docstring.strip()) < 80:
                return "Needs detail"
            return "Detailed"
        return documentation_status(self)


@dataclass(frozen=True)
class ModuleInfo:
    """A Python module and its discovered definitions."""

    path: Path
    relative_path: str
    module_name: str
    line_count: int
    docstring: str
    symbols: tuple[Symbol, ...]
    parse_error: str | None = None


def expression(node: ast.AST | None) -> str:
    """Format an optional AST expression as source-like Python text."""
    return ast.unparse(node) if node is not None else ""


def format_argument(argument: ast.arg, default: ast.expr | None = None) -> str:
    """Format one argument, including its annotation and default value."""
    rendered = argument.arg
    if argument.annotation is not None:
        rendered += f": {expression(argument.annotation)}"
    if default is not None:
        rendered += f" = {expression(default)}"
    return rendered


def format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Build a readable signature without importing or evaluating the function."""
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    defaults.extend(args.defaults)
    parts: list[str] = []

    for index, argument in enumerate(positional):
        parts.append(format_argument(argument, defaults[index]))
        if args.posonlyargs and index == len(args.posonlyargs) - 1:
            parts.append("/")

    if args.vararg is not None:
        vararg = "*" + format_argument(args.vararg)
        parts.append(vararg)
    elif args.kwonlyargs:
        parts.append("*")

    for argument, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        parts.append(format_argument(argument, default))

    if args.kwarg is not None:
        parts.append("**" + format_argument(args.kwarg))

    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    result = f"{prefix} {node.name}({', '.join(parts)})"
    if node.returns is not None:
        result += f" -> {expression(node.returns)}"
    return result + ":"


def function_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """Return named parameters, including positional-only and keyword-only ones."""
    values = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg is not None:
        values.append(node.args.vararg)
    if node.args.kwarg is not None:
        values.append(node.args.kwarg)
    return tuple(arg.arg for arg in values if arg.arg not in {"self", "cls"})


def has_non_none_return(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether the function declares a non-None return annotation."""
    if node.returns is None:
        return False
    annotation = expression(node.returns).replace(" ", "")
    return annotation not in {"None", "type(None)"}


def decorators_for(node: ast.AST) -> tuple[str, ...]:
    """Return decorators in source-like form."""
    return tuple(expression(decorator) for decorator in getattr(node, "decorator_list", ()))


class InventoryVisitor(ast.NodeVisitor):
    """Collect class and callable definitions while preserving their scope."""

    def __init__(self) -> None:
        self.scope: list[str] = []
        self.symbols: list[Symbol] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        """Record a class definition and visit its members."""
        qualified = ".".join([*self.scope, node.name])
        self.symbols.append(
            Symbol(
                kind="class",
                qualified_name=qualified,
                name=node.name,
                line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                signature=f"class {node.name}",
                docstring=ast.get_docstring(node, clean=True) or "",
                decorators=decorators_for(node),
            )
        )
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualified = ".".join([*self.scope, node.name])
        raised = any(isinstance(child, ast.Raise) for child in ast.walk(node))
        yielded = any(isinstance(child, (ast.Yield, ast.YieldFrom)) for child in ast.walk(node))
        self.symbols.append(
            Symbol(
                kind="function",
                qualified_name=qualified,
                name=node.name,
                line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                signature=format_signature(node),
                docstring=ast.get_docstring(node, clean=True) or "",
                decorators=decorators_for(node),
                parameters=function_parameters(node),
                returns_annotation=expression(node.returns) or None,
                has_raise=raised,
                has_yield=yielded,
            )
        )
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Collect a synchronous function definition."""
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        """Collect an asynchronous function definition."""
        self._visit_function(node)


def documentation_status(symbol: Symbol) -> str:
    """Classify a function docstring using minimum structural completeness rules."""
    doc = symbol.docstring.strip()
    if not doc:
        return "Missing"

    issues: list[str] = []
    if len(doc) < 100:
        issues.append("short summary")
    lower = doc.lower()
    has_parameters_section = any(
        re.search(rf"^\s*{re.escape(label)}:\s*$", doc, re.IGNORECASE | re.MULTILINE)
        for label in ("Args", "Arguments", "Parameters")
    )
    if symbol.parameters and not has_parameters_section:
        issues.append("missing Parameters section")
    if symbol.parameters and has_parameters_section:
        documented = {
            match.group(1).lstrip("*")
            for match in re.finditer(
                r"^\s{0,12}([*]{0,2}[A-Za-z_]\w*)(?:\s*\([^)]*\))?:",
                doc,
                re.MULTILINE,
            )
        }
        missing = sorted(set(symbol.parameters) - documented)
        if missing:
            issues.append("undocumented parameters: " + ", ".join(missing))
    if has_non_none_annotation_from_text(symbol.returns_annotation) and not re.search(
        r"^\s*(Returns|Yields):\s*$", doc, re.IGNORECASE | re.MULTILINE
    ):
        issues.append("missing Returns/Yields section")
    if symbol.has_raise and not re.search(r"^\s*Raises:\s*$", doc, re.IGNORECASE | re.MULTILINE):
        issues.append("raises exceptions but has no Raises section")

    return "Needs detail" if issues else "Detailed"


def has_non_none_annotation_from_text(annotation: str | None) -> bool:
    """Return whether rendered annotation text declares a value other than None."""
    if annotation is None:
        return False
    compact = annotation.replace(" ", "")
    return compact not in {"None", "type(None)"}


def source_files(sources: Iterable[str]) -> list[Path]:
    """Return unique production Python files under the configured source roots."""
    files: set[Path] = set()
    for source in sources:
        path = (REPO_ROOT / source).resolve()
        if not path.exists():
            continue
        if path.is_file() and path.suffix == ".py":
            candidates = [path]
        elif path.is_dir():
            candidates = path.rglob("*.py")
        else:
            candidates = []
        for candidate in candidates:
            relative = candidate.relative_to(REPO_ROOT)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if candidate.name.endswith("_test.py") or candidate.name.startswith("test_"):
                continue
            files.add(candidate)
    return sorted(files, key=lambda item: item.relative_to(REPO_ROOT).as_posix())


def inspect_modules(sources: Iterable[str]) -> list[ModuleInfo]:
    """Parse the selected Python files and collect their definitions."""
    modules: list[ModuleInfo] = []
    for path in source_files(sources):
        relative = path.relative_to(REPO_ROOT).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=relative)
        except (OSError, SyntaxError, UnicodeError) as exc:
            modules.append(
                ModuleInfo(
                    path=path,
                    relative_path=relative,
                    module_name=relative.removesuffix(".py").replace("/", "."),
                    line_count=0,
                    docstring="",
                    symbols=(),
                    parse_error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        visitor = InventoryVisitor()
        visitor.visit(tree)
        modules.append(
            ModuleInfo(
                path=path,
                relative_path=relative,
                module_name=relative.removesuffix(".py").replace("/", "."),
                line_count=len(source.splitlines()),
                docstring=ast.get_docstring(tree, clean=True) or "",
                symbols=tuple(
                    sorted(visitor.symbols, key=lambda item: (item.line, item.qualified_name))
                ),
            )
        )
    return modules


def escape_mdx_text(value: str) -> str:
    """Escape JSX-sensitive characters in prose while retaining Markdown syntax."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("{", "&#123;")
        .replace("}", "&#125;")
    )


def render_docstring(docstring: str) -> str:
    """Render a Google-style docstring as safe Markdown with useful section headings."""
    if not docstring.strip():
        return "*No source docstring is present for this definition.*"

    output: list[str] = []
    current_section: str | None = None
    previous_parameter: str | None = None
    for raw_line in docstring.splitlines():
        match = SECTION_RE.match(raw_line)
        if match:
            normalized = match.group(1).strip().lower()
            section_title = SECTION_NAMES.get(normalized)
            if section_title is not None:
                current_section = section_title
                previous_parameter = None
                output.extend(["", f"##### {section_title}", ""])
                continue

        if not raw_line.strip():
            output.append("")
            previous_parameter = None
            continue

        if current_section == "Parameters":
            parameter_match = PARAM_RE.match(raw_line)
            if parameter_match:
                name = parameter_match.group(1).lstrip("*")
                description = escape_mdx_text(parameter_match.group(2).strip())
                if description:
                    output.append(f"- **`{name}`** — {description}")
                else:
                    output.append(f"- **`{name}`**")
                previous_parameter = name
            elif raw_line[:1].isspace() and previous_parameter and output:
                output[-1] += " " + escape_mdx_text(raw_line.strip())
            else:
                output.append(escape_mdx_text(raw_line.strip()))
                previous_parameter = None
        else:
            output.append(escape_mdx_text(raw_line.strip()))

    return "\n".join(output).strip()


def slug_for_module(module: ModuleInfo) -> str:
    """Create a stable filename from a source-relative path."""
    return module.relative_path.removesuffix(".py").replace("/", "-") + "-py.md"


def render_symbol(symbol: Symbol, module: ModuleInfo) -> str:
    """Render one function or class with source location and documentation status."""
    source_url = (
        "https://github.com/ananthunalloor/kashengine/blob/main/"
        f"{module.relative_path}#L{symbol.line}"
    )
    depth = 4 if "." in symbol.qualified_name else 3
    heading = "#" * depth
    status = symbol.status
    lines = [
        f"{heading} `{symbol.qualified_name}`",
        "",
        f"**Documentation status:** `{status}`  ",
        f"**Source:** [`{module.relative_path}:{symbol.line}`]({source_url})  ",
        f"**Definition range:** lines {symbol.line}–{symbol.end_line}",
        "",
    ]
    if symbol.decorators:
        decorator_lines = [f"@{decorator}" for decorator in symbol.decorators]
        lines.extend(["**Decorators:**", "", "```python", *decorator_lines, "```", ""])
    if symbol.kind == "function":
        lines.extend(["```python", symbol.signature, "```", ""])
    else:
        lines.extend(["```python", symbol.signature + ":", "```", ""])
    lines.extend([render_docstring(symbol.docstring), ""])
    return "\n".join(lines)


def render_module(module: ModuleInfo) -> str:
    """Create the API page for one Python module."""
    title = module.module_name
    lines = [
        "---",
        f"title: {title}",
        "---",
        "",
        f"# `{title}`",
        "",
        f"**Source file:** `{module.relative_path}`  ",
        f"**Lines:** {module.line_count}  ",
        f"**Definitions found:** {len(module.symbols)}",
        "",
        "<!-- Generated file. Edit source docstrings, then regenerate the API reference. -->",
        "",
    ]
    if module.docstring:
        lines.extend(["## Module documentation", "", render_docstring(module.docstring), ""])
    if module.parse_error:
        lines.extend(["## Parse error", "", f"`{escape_mdx_text(module.parse_error)}`", ""])
    if not module.symbols:
        lines.extend(["No class or function definitions were found in this module.", ""])
    else:
        for symbol in module.symbols:
            lines.append(render_symbol(symbol, module))
    return "\n".join(lines).rstrip() + "\n"


def render_index(modules: list[ModuleInfo]) -> str:
    """Create the generated API reference landing page."""
    symbols = [
        symbol
        for module in modules
        for symbol in module.symbols
        if symbol.kind == "function"
    ]
    statuses = Counter(symbol.status for symbol in symbols)
    classes = sum(symbol.kind == "class" for module in modules for symbol in module.symbols)
    lines = [
        "---",
        "title: Python API reference",
        "slug: /reference/generated",
        "---",
        "",
        "# Python API reference",
        "",
        "This reference is generated from the Python source tree during the site build. "
        "It does not import application code.",
        "",
        f"**Modules:** {len(modules)}  ",
        f"**Functions and methods:** {len(symbols)}  ",
        f"**Classes:** {classes}  ",
        f"**Detailed function docstrings:** {statuses['Detailed']}  ",
        f"**Needs detail:** {statuses['Needs detail']}  ",
        f"**Missing docstrings:** {statuses['Missing']}",
        "",
        "The definition status is a minimum structural check. A `Detailed` status does not "
        "replace code review of the function contract. Check the coverage report to find "
        "entries that need documentation work.",
        "",
        "## Modules",
        "",
        "| Module | Definitions | Detailed | Needs detail | Missing |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for module in modules:
        functions = [symbol for symbol in module.symbols if symbol.kind == "function"]
        counts = Counter(symbol.status for symbol in functions)
        filename = slug_for_module(module)
        lines.append(
            f"| [`{module.module_name}`](./{filename}) | {len(module.symbols)} | "
            f"{counts['Detailed']} | {counts['Needs detail']} | {counts['Missing']} |"
        )
    lines.extend(
        [
            "",
            "## Documentation coverage",
            "",
            "The reference lists every function and method found in production source, including "
            "private and nested functions. Functions in tests and Django migrations are excluded "
            "because the reference targets the maintained application API rather than test "
            "helpers or historical migration implementations.",
            "",
            "Run `npm run api:check` from `docs/` to print the current backlog and exit with a "
            "non-zero status when any function does not meet the minimum documentation checks.",
            "",
            "See the [function documentation standard]"
            "(../../development/function-documentation.md) for the required contract details.",
            "",
        ]
    )
    return "\n".join(lines)


def render_coverage_report(
    modules: list[ModuleInfo],
) -> tuple[str, list[tuple[ModuleInfo, Symbol, str]]]:
    """Create a detailed backlog report and return the incomplete symbols."""
    functions = [
        (module, symbol)
        for module in modules
        for symbol in module.symbols
        if symbol.kind == "function"
    ]
    incomplete: list[tuple[ModuleInfo, Symbol, str]] = []
    counts = Counter(symbol.status for _, symbol in functions)
    lines = [
        "---",
        "title: Function documentation coverage",
        "---",
        "",
        "# Function documentation coverage",
        "",
        "Generated page. Do not edit by hand; improve source docstrings and rebuild the reference.",
        "",
        f"**Functions and methods:** {len(functions)}  ",
        f"**Detailed:** {counts['Detailed']}  ",
        f"**Needs detail:** {counts['Needs detail']}  ",
        f"**Missing:** {counts['Missing']}",
        "",
        "A function is marked `Needs detail` when its docstring is short, omits a parameter "
        "section, does not document every named parameter, omits a return section for a non-None "
        "return annotation, or contains a `raise` statement without a `Raises` section. These "
        "checks are mechanical and require human review as well.",
        "",
        "## Incomplete functions",
        "",
        "| Function | Source | Status | Improvement needed |",
        "| --- | --- | --- | --- |",
    ]
    for module, symbol in functions:
        if symbol.status == "Detailed":
            continue
        details: list[str] = []
        doc = symbol.docstring.strip()
        if not doc:
            details.append("Add a docstring describing purpose and contract")
        else:
            if len(doc) < 100:
                details.append("Expand the summary with behavior and constraints")
            has_args = bool(
                re.search(
                    r"^\s*(Args|Arguments|Parameters):\s*$",
                    doc,
                    re.IGNORECASE | re.MULTILINE,
                )
            )
            if symbol.parameters and not has_args:
                details.append("Add a Parameters section")
            elif symbol.parameters:
                documented = {
                    match.group(1).lstrip("*")
                    for match in re.finditer(
                        r"^\s{0,12}([*]{0,2}[A-Za-z_]\w*)(?:\s*\([^)]*\))?:",
                        doc,
                        re.MULTILINE,
                    )
                }
                missing = sorted(set(symbol.parameters) - documented)
                if missing:
                    details.append("Document: " + ", ".join(missing))
            if has_non_none_annotation_from_text(symbol.returns_annotation) and not re.search(
                r"^\s*(Returns|Yields):\s*$", doc, re.IGNORECASE | re.MULTILINE
            ):
                details.append("Add a Returns/Yields section")
            has_raises = re.search(
                r"^\s*Raises:\s*$", doc, re.IGNORECASE | re.MULTILINE
            )
            if symbol.has_raise and not has_raises:
                details.append("Document expected exceptions")
        source = f"{module.relative_path}:{symbol.line}"
        source_url = (
            "https://github.com/ananthunalloor/kashengine/blob/main/"
            f"{module.relative_path}#L{symbol.line}"
        )
        lines.append(
            f"| `{symbol.qualified_name}` | [`{source}`]({source_url}) | `{symbol.status}` | "
            f"{escape_mdx_text('; '.join(details))} |"
        )
        incomplete.append((module, symbol, "; ".join(details)))
    if not incomplete:
        lines.extend(["| — | — | — | No incomplete function docstrings were found. |"])
    lines.extend(
        [
            "",
            "Rebuild this page after improving source docstrings. Run `npm run api:check` "
            "to enforce the checks locally.",
            "",
        ]
    )
    return "\n".join(lines), incomplete


def write_output(modules: list[ModuleInfo], output: Path) -> None:
    """Write all generated Markdown files and remove stale generated module pages."""
    output.mkdir(parents=True, exist_ok=True)
    keep = {"index.md", "coverage-report.md"}
    for module in modules:
        keep.add(slug_for_module(module))
        (output / slug_for_module(module)).write_text(render_module(module), encoding="utf-8")
    for path in output.glob("*.md"):
        if path.name not in keep:
            path.unlink()
    (output / "index.md").write_text(render_index(modules), encoding="utf-8")
    coverage, _ = render_coverage_report(modules)
    (output / "coverage-report.md").write_text(coverage, encoding="utf-8")


def main() -> int:
    """Run API generation and optionally fail when the documentation is incomplete."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        help="Source root relative to the repository. May be supplied more than once.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=(
            "Output directory. Absolute paths are used directly; relative paths are "
            "repository-relative."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Generate the reference and exit with status 1 if any function needs more detail.",
    )
    args = parser.parse_args()
    sources = args.source if args.source is not None else list(DEFAULT_SOURCES)
    output = Path(args.output)
    if not output.is_absolute():
        output = REPO_ROOT / output

    modules = inspect_modules(sources)
    write_output(modules, output)
    all_functions = [
        symbol
        for module in modules
        for symbol in module.symbols
        if symbol.kind == "function"
    ]
    counts = Counter(symbol.status for symbol in all_functions)
    parse_errors = [module for module in modules if module.parse_error]
    print(
        f"Generated {len(modules)} module pages with {len(all_functions)} functions/methods: "
        f"{counts['Detailed']} detailed, {counts['Needs detail']} need detail, "
        f"{counts['Missing']} missing docstrings. Output: {output}"
    )
    if parse_errors:
        for module in parse_errors:
            print(f"Could not parse {module.relative_path}: {module.parse_error}", file=sys.stderr)
        return 2
    if args.check and any(symbol.status != "Detailed" for symbol in all_functions):
        print(
            "Function documentation coverage check failed. See coverage-report.md.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
