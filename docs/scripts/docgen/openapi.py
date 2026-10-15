"""Write the HTTP API reference pages (MDX) from the OpenAPI file.

The input is `docs/openapi/v1.json`, which `manage.py export_openapi` writes. This module reads
only that JSON file. It does not import Django or the project code.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from . import docstrings

if TYPE_CHECKING:
    from pathlib import Path

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
EXAMPLE_VALUES = {
    "date": "2026-10-12",
    "date-time": "2026-10-12T09:15:00+05:30",
    "uri": "https://example.com/page",
}
STATUS_TEXT = {
    "200": "OK",
    "401": "Unauthorized",
    "403": "Forbidden",
    "404": "Not Found",
    "422": "Unprocessable Content",
    "429": "Too Many Requests",
}


def load(path: Path) -> dict[str, Any]:
    """Read the OpenAPI document.

    Args:
        path: The JSON file.

    Returns:
        The parsed document.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def ref_name(ref: str) -> str:
    """Return the schema name at the end of a `$ref` string."""
    return ref.rsplit("/", 1)[-1]


def type_of(schema: dict[str, Any]) -> str:
    """Return a short readable type for a JSON schema, for example `array of Item`.

    Args:
        schema: A JSON schema object.

    Returns:
        A type text. Links are not made here. Names of other schemas appear as they are.
    """
    if "$ref" in schema:
        return ref_name(schema["$ref"])
    if "anyOf" in schema:
        parts = [type_of(item) for item in schema["anyOf"]]
        non_null = [part for part in parts if part != "null"]
        return " or ".join([*non_null, "null"] if len(non_null) != len(parts) else non_null)
    if "allOf" in schema:
        return " and ".join(type_of(item) for item in schema["allOf"])
    if "enum" in schema:
        return " | ".join(f'"{value}"' for value in schema["enum"])
    if "const" in schema:
        return f'"{schema["const"]}"'
    kind = schema.get("type", "any")
    if kind == "array":
        return f"array of {type_of(schema.get('items', {}))}"
    if kind == "object" and isinstance(schema.get("additionalProperties"), dict):
        return f"map of {type_of(schema['additionalProperties'])}"
    if "format" in schema:
        return f"{kind} ({schema['format']})"
    return str(kind)


def constraints(schema: dict[str, Any]) -> str:
    """Return the numeric limits and the default of a schema as text."""
    pool = [schema, *schema.get("anyOf", [])]
    found: list[str] = []
    for item in pool:
        for key, label in (("minimum", "min"), ("maximum", "max"), ("default", "default")):
            if key in item:
                found.append(f"{label} {item[key]}")
    return ", ".join(dict.fromkeys(found))


def example(schema: dict[str, Any], components: dict[str, Any], depth: int = 0) -> Any:
    """Build an example value from a schema. The value is fake and only shows the shape.

    Args:
        schema: A JSON schema object.
        components: The `components.schemas` mapping, to follow references.
        depth: The current depth. The function stops at 6 to avoid loops.

    Returns:
        A JSON-compatible value.
    """
    if depth > 6:
        return None
    if "$ref" in schema:
        return example(components[ref_name(schema["$ref"])], components, depth + 1)
    if "example" in schema:
        return schema["example"]
    for key in ("anyOf", "allOf"):
        if key in schema:
            options = [item for item in schema[key] if item.get("type") != "null"]
            return example(options[0], components, depth + 1) if options else None
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        props = schema.get("properties", {})
        out = {name: example(value, components, depth + 1) for name, value in props.items()}
        extra = schema.get("additionalProperties")
        if not props and isinstance(extra, dict):
            out = {"key": example(extra, components, depth + 1)}
        return out
    if kind == "array":
        return [example(schema.get("items", {}), components, depth + 1)]
    if kind == "string":
        return EXAMPLE_VALUES.get(schema.get("format", ""), "string")
    if kind == "integer":
        return schema.get("minimum", 1) if schema.get("minimum", 1) > 0 else 1
    if kind == "number":
        return 0.5
    if kind == "boolean":
        return True
    return None


def _slug(tag: str) -> str:
    return tag.lower().replace(" ", "-")


def _front(title: str, label: str, description: str, position: int | None = None) -> list[str]:
    lines = ["---", f"title: {title}", f"sidebar_label: {label}", f'description: "{description}"']
    if position is not None:
        lines.append(f"sidebar_position: {position}")
    return [*lines, "toc_max_heading_level: 3", "---", ""]


def _params_table(operation: dict[str, Any]) -> list[str]:
    params = operation.get("parameters", [])
    if not params:
        return []
    lines = [
        "**Parameters**",
        "",
        "| Name | In | Type | Required | Description |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in params:
        schema = item.get("schema", {})
        extra = constraints(schema)
        text = item.get("description", "") + (f" ({extra})" if extra else "")
        lines.append(
            f"| `{item['name']}` | {item['in']} | {docstrings.code_cell(type_of(schema))} | "
            f"{'yes' if item.get('required') else 'no'} | {docstrings.cell(text)} |"
        )
    return [*lines, ""]


def _response_table(operation: dict[str, Any]) -> list[str]:
    lines = ["**Responses**", "", "| Status | Meaning | Body |", "| --- | --- | --- |"]
    for status, response in sorted(operation["responses"].items(), key=lambda item: int(item[0])):
        body = response.get("content", {}).get("application/json", {}).get("schema")
        text = docstrings.code_cell(type_of(body)) if body else ""
        meaning = STATUS_TEXT.get(status, response.get("description", ""))
        lines.append(f"| `{status}` | {meaning} | {text} |")
    return [*lines, ""]


def _auth_line(operation: dict[str, Any]) -> str:
    if not operation.get("security"):
        return "**Authentication:** none."
    names = {"BearerToken": "Bearer token", "SessionCookie": "session cookie"}
    options = [names.get(next(iter(item), ""), "?") for item in operation["security"]]
    return "**Authentication:** " + " or ".join(options) + "."


def render_operation(
    path: str, method: str, operation: dict[str, Any], components: dict[str, Any]
) -> list[str]:
    """Return the MDX lines of one operation.

    Args:
        path: The URL path, for example `/api/v1/reports`.
        method: The lower-case HTTP method.
        operation: The operation object.
        components: The `components.schemas` mapping.

    Returns:
        The lines of the section.
    """
    op_id = operation["operationId"]
    lines = [f"## {operation['summary']} {{#{op_id}}}", "", f"`{method.upper()} {path}`", ""]
    lines += [docstrings.prose(operation.get("description", "")), "", _auth_line(operation), ""]
    lines += _params_table(operation)
    lines += _response_table(operation)
    ok = (
        operation["responses"]
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    query = ""
    required = [
        p for p in operation.get("parameters", []) if p.get("required") and p["in"] == "query"
    ]
    if required:
        query = "?" + "&".join(f"{p['name']}=..." for p in required)
    auth = "" if not operation.get("security") else ' \\\n  -H "Authorization: Bearer $KASH_TOKEN"'
    url_path = path.replace("{day}", "2026-10-12").replace("{ipo_id}", "42")
    lines += [
        "**Example request**",
        "",
        "```bash",
        f'curl -s "https://your-host{url_path}{query}"{auth}',
        "```",
        "",
    ]
    if ok:
        lines += [
            "**Example response** (`200`; the values show the shape, not real data)",
            "",
            "```json",
            json.dumps(example(ok, components), indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    return lines


def render_tag_page(
    tag: str,
    items: list[tuple[str, str, dict[str, Any]]],
    components: dict[str, Any],
    position: int,
) -> str:
    """Return the page of one tag (a group of operations)."""
    lines = _front(tag, tag, f"The {tag} endpoints of API v1.", position)
    lines += [f"# {tag}", ""]
    for path, method, operation in items:
        lines += render_operation(path, method, operation, components)
    return "\n".join(lines).rstrip() + "\n"


def render_schemas_page(components: dict[str, Any]) -> str:
    """Return the page that lists every response schema with its fields."""
    lines = _front("Schemas", "Schemas", "The JSON objects that API v1 returns.", 99)
    lines += [
        "# Schemas",
        "",
        "Every object that API v1 returns. A field marked `required` is always present.",
        "",
    ]
    for name, schema in sorted(components.items()):
        lines += [f"## {name} {{#schema-{name.lower()}}}", ""]
        if schema.get("description"):
            lines += [docstrings.prose(schema["description"]), ""]
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines += ["| Field | Type | Required | Description |", "| --- | --- | --- | --- |"]
        for field, value in props.items():
            extra = constraints(value)
            text = value.get("description", "") + (f" ({extra})" if extra else "")
            lines.append(
                f"| `{field}` | {docstrings.code_cell(type_of(value))} | "
                f"{'yes' if field in required else 'no'} | {docstrings.cell(text)} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_index(document: dict[str, Any], tags: list[str]) -> str:
    """Return the landing page of the HTTP API reference."""
    info = document["info"]
    lines = _front("HTTP API reference", "Overview", "Every endpoint of API v1.", 1)
    lines += [
        "# HTTP API reference",
        "",
        f"API {info['version']} (contract version). The pages below come from the OpenAPI file. "
        "[Download the OpenAPI file](pathname:///docs/openapi/v1.json).",
        "",
        "| Group | Endpoints |",
        "| --- | ---: |",
    ]
    counts: dict[str, int] = defaultdict(int)
    for item in document["paths"].values():
        for method, operation in item.items():
            if method in HTTP_METHODS:
                for tag in operation.get("tags", []):
                    counts[tag] += 1
    for tag in tags:
        lines.append(f"| [{tag}](./{_slug(tag)}.md) | {counts[tag]} |")
    lines += ["| [Schemas](./schemas.md) | |", ""]
    return "\n".join(lines)


def write(document: dict[str, Any], target: Path) -> list[str]:
    """Write all HTTP reference pages.

    Args:
        document: The parsed OpenAPI document.
        target: The output folder. The function empties it first.

    Returns:
        The tag names, in page order.
    """
    import shutil  # noqa: PLC0415

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    components = document.get("components", {}).get("schemas", {})
    grouped: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    for path, item in document["paths"].items():
        for method, operation in item.items():
            if method in HTTP_METHODS:
                grouped.setdefault(operation["tags"][0], []).append((path, method, operation))
    tags = list(grouped)
    (target / "index.md").write_text(render_index(document, tags), encoding="utf-8")
    for position, tag in enumerate(tags, start=2):
        (target / f"{_slug(tag)}.md").write_text(
            render_tag_page(tag, grouped[tag], components, position), encoding="utf-8"
        )
    (target / "schemas.md").write_text(render_schemas_page(components), encoding="utf-8")
    (target / "_category_.json").write_text(
        json.dumps({"label": "HTTP API reference", "position": 1}) + "\n", encoding="utf-8"
    )
    return tags
