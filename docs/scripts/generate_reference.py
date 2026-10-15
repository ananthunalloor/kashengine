#!/usr/bin/env python3
"""Generate the reference pages of the documentation site from the source tree.

The generator reads Python with `ast`. It never imports project code, so it cannot start Django,
open a connection, run task registration, or read a secret.

Usage:
    python docs/scripts/generate_reference.py              # write the pages
    python docs/scripts/generate_reference.py --check      # fail on a new docstring gap
    python docs/scripts/generate_reference.py --list       # print the docstring backlog
    python docs/scripts/generate_reference.py --write-baseline   # save the current gaps

The baseline (`docs/scripts/docstring_baseline.txt`) lists the gaps that exist today. `--check`
accepts the gaps in the baseline. It fails for a gap that is not in the baseline, and for a
baseline entry that is fixed (remove the line). The baseline can only get shorter.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docgen import checks, inventory, openapi, render, system

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "docs" / "reference" / "generated"
OPENAPI_FILE = REPO_ROOT / "docs" / "openapi" / "v1.json"
DEFAULT_STATIC = REPO_ROOT / "docs" / "static"
BASELINE_FILE = Path(__file__).resolve().parent / "docstring_baseline.txt"


def finding_key(item: checks.Finding) -> str:
    """Return the baseline key of a finding. It has no line number, so edits do not break it."""
    return f"{item.path}::{item.name}"


def read_baseline(path: Path) -> set[str]:
    """Return the keys in a baseline file. A missing file is an empty baseline."""
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def write_baseline(path: Path, found: list[checks.Finding]) -> None:
    """Write the keys of all findings to a baseline file, sorted."""
    header = (
        "# Docstring gaps that exist today. `generate_reference.py --check` accepts them.\n"
        "# Fix a gap, then remove its line. Do not add a line for new code: write the docstring.\n"
    )
    keys = sorted({finding_key(item) for item in found})
    path.write_text(header + "\n".join(keys) + "\n", encoding="utf-8")


def write_python_reference(
    modules: list[inventory.Module], output: Path, ctx: render.Context
) -> None:
    """Write the Python reference under `<output>/python`."""
    target = output / "python"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    groups = inventory.groups(modules)
    (target / "index.md").write_text(render.render_overview(modules, groups), encoding="utf-8")
    (target / "coverage.md").write_text(render.render_coverage(modules, ctx), encoding="utf-8")
    for position, group in enumerate(groups, start=1):
        folder = target / group.name
        folder.mkdir()
        (folder / "_category_.json").write_text(
            json.dumps({"label": group.name, "position": position, "collapsed": True}) + "\n",
            encoding="utf-8",
        )
        (folder / "index.md").write_text(render.render_group(group), encoding="utf-8")
        for module in group.modules:
            if module.has_code:
                (folder / f"{render.module_slug(module)}.md").write_text(
                    render.render_module(module, ctx), encoding="utf-8"
                )


def main(argv: list[str] | None = None) -> int:
    """Run the generator. Return the process exit code."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        action="append",
        help="Source root, relative to the repository. Repeat to add more.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output folder.")
    parser.add_argument(
        "--static",
        default=str(DEFAULT_STATIC),
        help="Folder for files that the site serves as they are (the OpenAPI file).",
    )
    parser.add_argument(
        "--ref", default=os.environ.get("DOCS_SOURCE_REF", "main"), help="Git ref for source links."
    )
    parser.add_argument(
        "--check", action="store_true", help="Exit with 1 if a docstring is incomplete."
    )
    parser.add_argument("--list", action="store_true", help="Print every incomplete definition.")
    parser.add_argument(
        "--baseline",
        default=str(BASELINE_FILE),
        help="File with the accepted gaps. Use an empty name to check without a baseline.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Save all current gaps as the baseline and exit.",
    )
    parser.add_argument(
        "--no-write", action="store_true", help="Do not write pages (use with --check or --list)."
    )
    args = parser.parse_args(argv)

    output = Path(args.output)
    if not output.is_absolute():
        output = REPO_ROOT / output
    modules = inventory.inspect(REPO_ROOT, args.source or inventory.DEFAULT_SOURCES)
    errors = [module for module in modules if module.parse_error]
    for module in errors:
        print(f"Cannot parse {module.path}: {module.parse_error}", file=sys.stderr)
    if errors:
        return 2

    found = checks.findings(modules)
    if not args.no_write:
        write_python_reference(modules, output, render.Context(ref=args.ref))
        system.write(REPO_ROOT, output / "system")
        if OPENAPI_FILE.exists():
            openapi.write(openapi.load(OPENAPI_FILE), output / "http")
            static = Path(args.static) / "openapi"
            static.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(OPENAPI_FILE, static / "v1.json")
    symbols = sum(len(module.symbols) for module in modules)
    print(f"{len(modules)} modules, {symbols} definitions, {len(found)} docstrings to fix.")
    if args.write_baseline:
        write_baseline(Path(args.baseline or BASELINE_FILE), found)
        print(f"Baseline saved: {len({finding_key(item) for item in found})} entries.")
        return 0
    if args.list:
        for item in found:
            print(item)
    if not args.check:
        return 0
    return check_against_baseline(
        found, Path(args.baseline) if args.baseline else None, partial=bool(args.source)
    )


def check_against_baseline(
    found: list[checks.Finding], baseline: Path | None, *, partial: bool = False
) -> int:
    """Print the new gaps and the stale baseline entries. Return the exit code.

    Args:
        found: All gaps that the generator found.
        baseline: The baseline file, or None to accept nothing.
        partial: True when only some source roots were scanned. Then a baseline entry that
            is not found is not an error, because the generator did not look at its file.

    Returns:
        0 if there are no new gaps and no stale entries, else 1.
    """
    accepted = read_baseline(baseline) if baseline else set()
    new = [item for item in found if finding_key(item) not in accepted]
    stale = [] if partial else sorted(accepted - {finding_key(item) for item in found})
    for item in new:
        print(f"NEW: {item}", file=sys.stderr)
    for key in stale:
        print(f"FIXED, remove from the baseline: {key}", file=sys.stderr)
    if accepted:
        print(f"{len(found) - len(new)} gaps are in the baseline.")
    return 1 if new or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
