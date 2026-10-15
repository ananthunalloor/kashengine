"""Read the Python source with `ast` and list its modules, classes and functions.

The code under test is never imported. This keeps the build safe: it cannot start Django,
open a connection, run a task registration, or read a secret.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

ROUTE_DECORATOR = re.compile(r"""^\w+\.(get|post|put|patch|delete)\(["']/""")
DEFAULT_SOURCES = ("apps", "config", "manage.py")
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
FIELD_SUFFIXES = ("Field", "ForeignKey", "OneToOneField", "ManyToManyField")
ENUM_BASES = {"TextChoices", "IntegerChoices", "Choices", "Enum", "StrEnum", "IntEnum"}
PROPERTY_DECORATORS = {"property", "cached_property", "functools.cached_property"}


@dataclass(frozen=True)
class Param:
    """One parameter of a function."""

    name: str  # With the leading stars for *args and **kwargs.
    annotation: str
    default: str


@dataclass(frozen=True)
class Member:
    """A model field, an enum member or a module constant."""

    name: str
    kind: str  # The field class, or the Python type of a constant.
    value: str  # The call arguments, the enum value or the constant value.
    line: int = 0


@dataclass(frozen=True)
class Symbol:
    """A class, a method or a function."""

    kind: str  # class, function, method
    qualified_name: str
    name: str
    line: int
    end_line: int
    signature: str
    docstring: str
    decorators: tuple[str, ...] = ()
    params: tuple[Param, ...] = ()
    returns: str = ""
    raises: tuple[str, ...] = ()  # Names of exceptions that the body raises explicitly.
    is_generator: bool = False
    is_nested: bool = False
    bases: tuple[str, ...] = ()
    members: tuple[Member, ...] = ()
    statements: int = 0

    @property
    def is_private(self) -> bool:
        """True for a name that starts with one underscore (not a dunder)."""
        return self.name.startswith("_") and not self.is_dunder

    @property
    def is_dunder(self) -> bool:
        """True for a name like `__str__`."""
        return self.name.startswith("__") and self.name.endswith("__")

    @property
    def is_property(self) -> bool:
        """True for a property or a cached property."""
        return any(
            item in PROPERTY_DECORATORS or item.endswith((".setter", ".getter", ".deleter"))
            for item in self.decorators
        )

    @property
    def is_route(self) -> bool:
        """True for a django-ninja route function, such as `@router.get("/x")`.

        The docstring of a route is the public description in the OpenAPI file. It does not
        have `Args` or `Returns` sections, because the parameters and the response are in the
        OpenAPI file too.
        """
        return any(ROUTE_DECORATOR.match(item) for item in self.decorators)

    @property
    def is_overload(self) -> bool:
        """True for a typing overload stub."""
        return any(item.split(".")[-1] == "overload" for item in self.decorators)


@dataclass(frozen=True)
class Module:
    """A Python file and what it defines."""

    path: str  # Relative to the repository root, with forward slashes.
    name: str  # The dotted module name.
    group: str  # The app name, or "config".
    short_name: str  # The module name without the group.
    lines: int
    docstring: str
    symbols: tuple[Symbol, ...]
    constants: tuple[Member, ...] = ()
    parse_error: str = ""
    has_code: bool = True


def expr(node: ast.AST | None) -> str:
    """Return the source text of an expression."""
    return ast.unparse(node) if node is not None else ""


def _param(arg: ast.arg, default: ast.expr | None, prefix: str = "") -> Param:
    return Param(prefix + arg.arg, expr(arg.annotation), expr(default))


def params_of(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[Param, ...]:
    """Return all parameters, including self and cls (callers can drop them)."""
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    defaults.extend(args.defaults)
    out = [_param(arg, defaults[i]) for i, arg in enumerate(positional)]
    if args.vararg:
        out.append(_param(args.vararg, None, "*"))
    out.extend(
        _param(arg, default) for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True)
    )
    if args.kwarg:
        out.append(_param(args.kwarg, None, "**"))
    return tuple(out)


def signature_of(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return a one-line `def` signature without the body."""
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    defaults.extend(args.defaults)

    def render(arg: ast.arg, default: ast.expr | None, prefix: str = "") -> str:
        text = prefix + arg.arg
        if arg.annotation is not None:
            text += f": {expr(arg.annotation)}"
        if default is not None:
            text += (" = " if arg.annotation is not None else "=") + expr(default)
        return text

    parts: list[str] = []
    for index, arg in enumerate(positional):
        parts.append(render(arg, defaults[index]))
        if args.posonlyargs and index == len(args.posonlyargs) - 1:
            parts.append("/")
    if args.vararg:
        parts.append(render(args.vararg, None, "*"))
    elif args.kwonlyargs:
        parts.append("*")
    parts.extend(
        render(arg, default) for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True)
    )
    if args.kwarg:
        parts.append(render(args.kwarg, None, "**"))
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    text = f"{prefix} {node.name}({', '.join(parts)})"
    if node.returns is not None:
        text += f" -> {expr(node.returns)}"
    return text


def _own_nodes(node: ast.AST):
    """Walk a function body without going into nested functions or classes."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda):
            continue
        stack.extend(ast.iter_child_nodes(current))


def _raised_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    names: list[str] = []
    for child in _own_nodes(node):
        if isinstance(child, ast.Raise) and child.exc is not None:
            target = child.exc.func if isinstance(child.exc, ast.Call) else child.exc
            names.append(expr(target))
    return tuple(dict.fromkeys(names))


def _is_generator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(isinstance(child, ast.Yield | ast.YieldFrom) for child in _own_nodes(node))


def _count_statements(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    return sum(isinstance(child, ast.stmt) for child in _own_nodes(node))


def _literal(node: ast.expr) -> str | None:
    """Return the text of a simple constant, or None when the value is not a plain literal."""
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    text = repr(value)
    return text if len(text) <= 120 else text[:117] + "..."


def _callee(node: ast.expr) -> str:
    return expr(node.func) if isinstance(node, ast.Call) else ""


class _Collector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[tuple[str, str]] = []  # (kind, name)
        self.symbols: list[Symbol] = []

    def _qualified(self, name: str) -> str:
        return ".".join([*(item[1] for item in self.scope), name])

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Record a class and visit its members."""
        bases = tuple(expr(base) for base in node.bases)
        members = self._class_members(node, bases)
        self.symbols.append(
            Symbol(
                kind="class",
                qualified_name=self._qualified(node.name),
                name=node.name,
                line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                signature=f"class {node.name}" + (f"({', '.join(bases)})" if bases else ""),
                docstring=ast.get_docstring(node, clean=True) or "",
                decorators=tuple(expr(item) for item in node.decorator_list),
                bases=bases,
                members=members,
                is_nested=any(kind == "function" for kind, _ in self.scope),
            )
        )
        self.scope.append(("class", node.name))
        self.generic_visit(node)
        self.scope.pop()

    @staticmethod
    def _class_members(node: ast.ClassDef, bases: tuple[str, ...]) -> tuple[Member, ...]:
        is_enum = any(base.split(".")[-1] in ENUM_BASES for base in bases)
        members: list[Member] = []
        for item in node.body:
            if isinstance(item, ast.Assign) and len(item.targets) == 1:
                target, value = item.targets[0], item.value
            elif isinstance(item, ast.AnnAssign) and item.value is not None:
                target, value = item.target, item.value
            else:
                continue
            if not isinstance(target, ast.Name) or target.id.startswith("_"):
                continue
            callee = _callee(value)
            if callee.split(".")[-1].endswith(FIELD_SUFFIXES):
                args = [expr(arg) for arg in value.args]  # ty: ignore[unresolved-attribute]
                args += [f"{kw.arg}={expr(kw.value)}" for kw in value.keywords]  # ty: ignore[unresolved-attribute]
                members.append(Member(target.id, callee, ", ".join(args), item.lineno))
            elif is_enum and target.id.isupper():
                members.append(Member(target.id, "member", expr(value), item.lineno))
        return tuple(members)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        in_class = bool(self.scope) and self.scope[-1][0] == "class"
        nested = any(kind == "function" for kind, _ in self.scope)
        params = params_of(node)
        if in_class and params and params[0].name in {"self", "cls"}:
            params = params[1:]
        self.symbols.append(
            Symbol(
                kind="method" if in_class else "function",
                qualified_name=self._qualified(node.name),
                name=node.name,
                line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                signature=signature_of(node),
                docstring=ast.get_docstring(node, clean=True) or "",
                decorators=tuple(expr(item) for item in node.decorator_list),
                params=params,
                returns=expr(node.returns),
                raises=_raised_names(node),
                is_generator=_is_generator(node),
                is_nested=nested,
                statements=_count_statements(node),
            )
        )
        self.scope.append(("function", node.name))
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Record a function or method."""
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Record an async function or method."""
        self._visit_function(node)


def _constants(tree: ast.Module) -> tuple[Member, ...]:
    found: list[Member] = []
    for item in tree.body:
        if isinstance(item, ast.Assign) and len(item.targets) == 1:
            target, value = item.targets[0], item.value
        elif isinstance(item, ast.AnnAssign) and item.value is not None:
            target, value = item.target, item.value
        else:
            continue
        if not isinstance(target, ast.Name) or not target.id.isupper() or target.id.startswith("_"):
            continue
        text = _literal(value)
        if text is not None:
            found.append(
                Member(target.id, type(ast.literal_eval(value)).__name__, text, item.lineno)
            )
    return tuple(found)


def source_files(root: Path, sources: tuple[str, ...] | list[str]) -> list[Path]:
    """Return the production Python files under the given source roots."""
    files: set[Path] = set()
    for source in sources:
        path = (root / source).resolve()
        if path.is_file() and path.suffix == ".py":
            candidates = [path]
        elif path.is_dir():
            candidates = list(path.rglob("*.py"))
        else:
            continue
        for candidate in candidates:
            relative = candidate.relative_to(root)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if candidate.name.startswith("test_") or candidate.name.endswith("_test.py"):
                continue
            if relative.as_posix() == "apps/__init__.py":
                continue  # The empty marker of the apps folder. It is not a package of its own.
            files.add(candidate)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def group_of(relative: str) -> tuple[str, str]:
    """Return (group, short module name) for a repository-relative path."""
    parts = relative.removesuffix(".py").split("/")
    if parts[0] == "apps" and len(parts) > 1:
        group, rest = parts[1], parts[2:]
    elif parts[0] == "config":
        group, rest = "config", parts[1:]
    else:
        group, rest = "config", parts
    rest = [item for item in rest if item != "__init__"]
    return group, ".".join(rest) or "package"


def inspect(root: Path, sources: tuple[str, ...] | list[str] = DEFAULT_SOURCES) -> list[Module]:
    """Parse the selected files and return one `Module` for each."""
    modules: list[Module] = []
    for path in source_files(root, sources):
        relative = path.relative_to(root).as_posix()
        dotted = relative.removesuffix(".py").replace("/", ".").removesuffix(".__init__")
        group, short = group_of(relative)
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=relative)
        except (OSError, SyntaxError, UnicodeError) as exc:
            modules.append(
                Module(
                    relative,
                    dotted,
                    group,
                    short,
                    0,
                    "",
                    (),
                    parse_error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        collector = _Collector()
        collector.visit(tree)
        body = [item for item in tree.body if not _is_docstring(item)]
        modules.append(
            Module(
                path=relative,
                name=dotted,
                group=group,
                short_name=short,
                lines=len(text.splitlines()),
                docstring=ast.get_docstring(tree, clean=True) or "",
                symbols=tuple(
                    sorted(collector.symbols, key=lambda item: (item.line, item.qualified_name))
                ),
                constants=_constants(tree),
                has_code=bool(body),
            )
        )
    return modules


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


@dataclass(frozen=True)
class Group:
    """The modules of one app."""

    name: str
    modules: tuple[Module, ...] = field(default_factory=tuple)


def groups(modules: list[Module]) -> list[Group]:
    """Return the modules grouped by app name, in alphabetical order."""
    by_name: dict[str, list[Module]] = {}
    for module in modules:
        by_name.setdefault(module.group, []).append(module)
    return [Group(name, tuple(items)) for name, items in sorted(by_name.items())]
