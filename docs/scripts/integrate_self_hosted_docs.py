#!/usr/bin/env python3
"""Integrate the Docusaurus service with the repository's existing deployment files.

The main Docusaurus patch intentionally adds files only. Run this script once after
applying the patch. It locates configuration anchors in the current checkout, checks
all required transformations before writing, and is safe to run more than once.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]

COMMON_DOCS_SERVICE = '''  # Static Docusaurus site. Caddy exposes it under /docs/; do not publish a host port.
  docs:
    build:
      context: .
      dockerfile: docs/Dockerfile
      args:
        DOCS_URL: "https://${SITE_ADDRESS:-localhost}"
    restart: unless-stopped
'''

PROD_DOCS_SERVICE = '''  docs:
    <<: *hardened
    read_only: true
    tmpfs:
      - /tmp
    networks:
      - proxy
'''

DOCS_CSP = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"


def read(path: str) -> str:
    file_path = ROOT / path
    if not file_path.is_file():
        raise RuntimeError(f"Required file not found: {path}")
    return file_path.read_text(encoding="utf-8")


def service_block(text: str, name: str) -> tuple[int, int] | None:
    """Return a top-level Compose service block (two-space service indentation)."""
    match = re.search(rf"(?m)^  {re.escape(name)}:\s*$", text)
    if not match:
        return None
    following = re.search(r"(?m)^  [A-Za-z0-9_-]+:\s*$", text[match.end():])
    end = match.end() + following.start() if following else len(text)
    return match.start(), end


def ensure_caddy_dependency(text: str) -> str:
    span = service_block(text, "caddy")
    if span is None:
        raise RuntimeError("Could not find the top-level 'caddy' service in docker-compose.yml")
    start, end = span
    block = text[start:end]
    if re.search(r"^ {6}docs:\s*$|^ {6}-\s+docs\s*$", block, re.M):
        return text

    dep = re.search(r"(?m)^ {4}depends_on:\s*\n", block)
    if not dep:
        block = block.rstrip("\n") + "\n    depends_on:\n      docs:\n        condition: service_healthy\n"
    else:
        # Collect only the dependency entries. Stop when the next service field starts.
        children_start = dep.end()
        lines = block[children_start:].splitlines(keepends=True)
        insert_at = children_start
        children: list[str] = []
        for line in lines:
            if not line.strip():
                insert_at += len(line)
                children.append(line)
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent <= 4:
                break
            insert_at += len(line)
            children.append(line)
        child_text = "".join(children)
        if re.search(r"(?m)^ {6}[A-Za-z0-9_-]+:\s*$", child_text):
            addition = "      docs:\n        condition: service_healthy\n"
        block = block[:insert_at] + addition + block[insert_at:]
        # Ensure the addition remains in the mapping even if the block used CRLF originally.
    return text[:start] + block + text[end:]


def add_common_service(text: str) -> str:
    if service_block(text, "docs") is None:
        anchor = re.search(r"(?m)^  caddy:\s*$", text)
        if not anchor:
            raise RuntimeError("Could not find the top-level 'caddy' service in docker-compose.yml")
        text = text[:anchor.start()] + COMMON_DOCS_SERVICE + text[anchor.start():]
    return ensure_caddy_dependency(text)


def add_prod_service(text: str) -> str:
    if service_block(text, "docs") is not None:
        return text
    web = re.search(r"(?m)^  web:\s*$", text)
    if not web:
        raise RuntimeError("Could not find the top-level 'web' service in docker-compose.prod.yml")
    return text[:web.start()] + PROD_DOCS_SERVICE + text[web.start():]


def find_proxy_directive(text: str) -> tuple[int, int, str]:
    """Find the web reverse-proxy directive and return its full block, if braced."""
    match = re.search(r"(?m)^(?P<indent>[ \t]*)reverse_proxy\s+web:8000\b[^\n]*\n?", text)
    if not match:
        raise RuntimeError(
            "Could not find 'reverse_proxy web:8000' in deploy/caddy/Caddyfile. "
            "No files were written; inspect the current Caddy routing and adapt the script."
        )
    start = match.start()
    first_line_end = text.find("\n", match.start())
    if first_line_end < 0:
        first_line_end = len(text)
    first_line = text[start:first_line_end]
    if "{" not in first_line:
        return start, first_line_end, text[start:first_line_end]
    depth = first_line.count("{") - first_line.count("}")
    pos = first_line_end + 1
    while depth > 0:
        line_end = text.find("\n", pos)
        if line_end < 0:
            line_end = len(text)
        line = text[pos:line_end]
        depth += line.count("{") - line.count("}")
        pos = line_end + 1
    if depth != 0:
        raise RuntimeError("Could not find the end of the existing Caddy reverse_proxy block")
    return start, pos, text[start:pos].rstrip("\n")


def add_caddy_routes(text: str) -> str:
    if "@docs_root path /docs" in text and "reverse_proxy docs:8080" in text:
        return text
    start, end, original_proxy = find_proxy_directive(text)
    indent_match = re.match(r"[ \t]*", original_proxy)
    indent = indent_match.group(0) if indent_match else "\t"
    child = indent + "\t"
    grandchild = child + "\t"
    # Preserve every directive from the existing application reverse_proxy block.
    original_lines = original_proxy.splitlines()
    indented_original = "\n".join(
        child + line[len(indent):] if line.startswith(indent) else child + line
        for line in original_lines
    )
    replacement = (
        f"{indent}# Redirect the prefix root so Docusaurus assets stay beneath /docs/.\n"
        f"{indent}@docs_root path /docs\n"
        f"{indent}redir @docs_root /docs/ 308\n"
        f"{indent}handle_path /docs/* {{\n"
        f"{child}reverse_proxy docs:8080 {{\n"
        f"{grandchild}header_down -Server\n"
        f"{child}}}\n"
        f"{indent}}}\n"
        f"{indent}handle {{\n"
        f"{indented_original}\n"
        f"{indent}}}"
    )
    return text[:start] + replacement + "\n" + text[end:]


def scope_csp_for_docs(text: str) -> str:
    if "@docs_path path /docs /docs/*" in text:
        return text
    match = re.search(r"(?ms)^(?P<indent>[ \t]*)header\s*\{\n(?P<body>.*?)(?P=indent)\}", text)
    if not match or "Content-Security-Policy" not in match.group("body"):
        raise RuntimeError("Could not find the existing Caddy security-header block")
    indent = match.group("indent")
    body_lines = [line.rstrip() for line in match.group("body").splitlines() if line.strip()]
    csp_line = next((line for line in body_lines if "Content-Security-Policy" in line), None)
    if csp_line is None:
        raise RuntimeError("Could not find the Content-Security-Policy directive")
    other_lines = [line for line in body_lines if "Content-Security-Policy" not in line]

    def make_header(name: str, policy: str) -> list[str]:
        rows = [f"{indent}header {name} {{", f"{indent}\t{policy}"]
        rows.extend(f"{indent}\t{line.strip()}" for line in other_lines)
        rows.append(f"{indent}}}")
        return rows

    rows = [
        f"{indent}@docs_path path /docs /docs/*",
        *make_header("@docs_path", f'{{$CSP_HEADER:Content-Security-Policy}} "{DOCS_CSP}"'),
        f"{indent}@application_path not path /docs /docs/*",
        *make_header("@application_path", csp_line.strip()),
    ]
    return text[:match.start()] + "\n".join(rows) + text[match.end():]


def update_dockerignore(text: str) -> str:
    required = ["docs/node_modules/", "docs/build/", "docs/.docusaurus/", "docs/docs/reference/generated/"]
    missing = [line for line in required if line not in text.splitlines()]
    if not missing:
        return text
    return text.rstrip("\n") + "\n\n# Docusaurus local build artifacts\n" + "\n".join(missing) + "\n"


def update_readme(text: str) -> str:
    if "/docs/" in text or "docs/docs/index.md" in text:
        return text
    addition = (
        "\n## Developer documentation\n\n"
        "The self-hosted Docusaurus site is available at `/docs/` after you start the stack. "
        "Its source content is in [`docs/docs/`](docs/docs/index.md).\n"
    )
    return text.rstrip("\n") + "\n" + addition


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate anchors without writing files.")
    args = parser.parse_args()
    try:
        planned = {
            "docker-compose.yml": add_common_service(read("docker-compose.yml")),
            "docker-compose.prod.yml": add_prod_service(read("docker-compose.prod.yml")),
        }
        caddy = scope_csp_for_docs(read("deploy/caddy/Caddyfile"))
        planned["deploy/caddy/Caddyfile"] = add_caddy_routes(caddy)
        planned[".dockerignore"] = update_dockerignore(read(".dockerignore"))
        planned["README.md"] = update_readme(read("README.md"))
    except (OSError, RuntimeError) as exc:
        print(f"Docs integration failed: {exc}", file=sys.stderr)
        return 2

    changed = [path for path, content in planned.items() if (ROOT / path).read_text(encoding="utf-8") != content]
    if args.check:
        for path in changed:
            print(f"Would update {path}")
        if not changed:
            print("Documentation integration is already present.")
        return 0

    # Validate every target before the first write. Writes use rename to avoid partial files.
    for path, content in planned.items():
        destination = ROOT / path
        old_mode = destination.stat().st_mode
        temporary = destination.with_name(destination.name + ".docs-integration.tmp")
        temporary.write_text(content, encoding="utf-8", newline="")
        os.chmod(temporary, old_mode)
        os.replace(temporary, destination)
    for path in changed:
        print(f"Updated {path}")
    if not changed:
        print("Documentation integration is already present.")
    print("Review with: git diff -- docker-compose.yml docker-compose.prod.yml deploy/caddy/Caddyfile .dockerignore README.md")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
