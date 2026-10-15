"""The docstring contract. Each rule here is also written in the developer guide.

A docstring is `Complete` when it passes every rule that applies to its definition.
The rules are mechanical. They find missing parts, not wrong text. A review still decides
if the text is correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import docstrings

if TYPE_CHECKING:
    from .inventory import Module, Symbol

COMPLETE = "Complete"
INCOMPLETE = "Incomplete"
MISSING = "Missing"
NO_VALUE = {"", "None", "NoReturn", "Never", "typing.NoReturn", "typing.Never"}


@dataclass(frozen=True)
class Finding:
    """A definition that does not meet the contract."""

    path: str
    line: int
    name: str
    status: str
    problems: tuple[str, ...]

    def __str__(self) -> str:
        """Format like a linter message: `path:line: name: problem; problem`."""
        return f"{self.path}:{self.line}: {self.name}: {'; '.join(self.problems)}"


def is_exempt(symbol: Symbol) -> bool:
    """True for definitions that the reference does not require a docstring for."""
    return symbol.is_overload or "Meta" in symbol.qualified_name.split(".")


def problems_for(symbol: Symbol) -> tuple[str, ...]:
    """Return what is wrong with the docstring of one definition. An empty tuple means none."""
    text = symbol.docstring.strip()
    if not text:
        return ("no docstring",)
    doc = docstrings.parse(text)
    problems: list[str] = []
    if not doc.summary:
        problems.append("no summary line")
    if symbol.kind == "class" or symbol.is_nested or symbol.is_dunder or symbol.is_route:
        return tuple(problems)

    params = [item.name for item in symbol.params if item.name.lstrip("*") not in {"_"}]
    documented = doc.documented_params
    if params:
        if not any(section.name in docstrings.PARAM_SECTIONS for section in doc.sections):
            problems.append("no Args section for: " + ", ".join(params))
        else:
            missing = [name for name in params if name.lstrip("*") not in documented]
            if missing:
                problems.append("Args does not list: " + ", ".join(missing))
            known = {name.lstrip("*") for name in params}
            unknown = sorted(documented - known)
            if unknown:
                problems.append("Args lists names that are not parameters: " + ", ".join(unknown))

    simple = symbol.statements <= 1 and not symbol.params
    if symbol.returns not in NO_VALUE and not symbol.is_property and not simple:
        label = "Yields" if symbol.is_generator else "Returns"
        if not doc.section("yields", "returns", "return"):
            problems.append(f"no {label} section")
    if symbol.raises and not doc.section("raises"):
        problems.append("no Raises section for: " + ", ".join(symbol.raises))
    return tuple(problems)


def module_problems(module: Module) -> tuple[str, ...]:
    """Return what is wrong with the module docstring."""
    if not module.has_code:
        return ()
    if not module.docstring.strip():
        return ("no module docstring",)
    return () if docstrings.parse(module.docstring).summary else ("no summary line",)


def status_of(symbol: Symbol) -> str:
    """Return Complete, Incomplete or Missing for one definition."""
    problems = problems_for(symbol)
    if not problems:
        return COMPLETE
    return MISSING if problems == ("no docstring",) else INCOMPLETE


def findings(modules: list[Module]) -> list[Finding]:
    """Return every definition and module that does not meet the contract."""
    found: list[Finding] = []
    for module in modules:
        problems = module_problems(module)
        if problems:
            status = MISSING if problems == ("no module docstring",) else INCOMPLETE
            found.append(Finding(module.path, 1, "<module>", status, problems))
        for symbol in module.symbols:
            if is_exempt(symbol):
                continue
            problems = problems_for(symbol)
            if problems:
                found.append(
                    Finding(
                        module.path,
                        symbol.line,
                        symbol.qualified_name,
                        MISSING if problems == ("no docstring",) else INCOMPLETE,
                        problems,
                    )
                )
    return found
