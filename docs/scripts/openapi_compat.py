#!/usr/bin/env python3
"""Compare two OpenAPI files and list the breaking changes.

Inside one major version, the API may only add things. This script reads an old file and a new
file. It prints each change that can break a client, and it exits with 1 if it finds one.

Usage:
    python docs/scripts/openapi_compat.py OLD.json NEW.json

CI uses the file on the main branch as OLD and the file of the pull request as NEW.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
Json = dict[str, Any]


def resolve(schema: Json, components: Json, seen: tuple[str, ...] = ()) -> Json:
    """Follow `$ref` links at the top of a schema.

    Args:
        schema: A JSON schema.
        components: The `components.schemas` mapping.
        seen: Names that were already followed. It stops a loop.

    Returns:
        The schema that the reference points to, or the schema itself.
    """
    ref = schema.get("$ref")
    if not ref:
        return schema
    name = ref.rsplit("/", 1)[-1]
    if name in seen:
        return {}
    return resolve(components.get(name, {}), components, (*seen, name))


def kinds(schema: Json, components: Json) -> set[str]:
    """Return the set of JSON types that a schema allows (`anyOf` is expanded)."""
    schema = resolve(schema, components)
    if "anyOf" in schema:
        found: set[str] = set()
        for item in schema["anyOf"]:
            found |= kinds(item, components)
        return found
    if "enum" in schema:
        return {"enum"} if "type" not in schema else {schema["type"]}
    return {str(schema.get("type", "any"))}


def maximum(schema: Json) -> float | None:
    """Return the `maximum` of a schema, also from an `anyOf` branch."""
    found = [item["maximum"] for item in [schema, *schema.get("anyOf", [])] if "maximum" in item]
    return min(found) if found else None


def enum_values(schema: Json, components: Json) -> set[str]:
    """Return the enum values of a schema (`anyOf` is expanded)."""
    schema = resolve(schema, components)
    values = {str(v) for v in schema.get("enum", [])}
    for item in schema.get("anyOf", []):
        values |= enum_values(item, components)
    return values


def compare_response(
    path: str, old: Json, new: Json, old_c: Json, new_c: Json, where: str, depth: int = 0
) -> list[str]:
    """Compare a response schema. A removed field or a changed type breaks a client.

    Args:
        path: The endpoint, for the message.
        old: The old schema.
        new: The new schema.
        old_c: The old `components.schemas`.
        new_c: The new `components.schemas`.
        where: The field path, for the message.
        depth: The depth. It stops at 8.

    Returns:
        The messages of the breaking changes.
    """
    if depth > 8:
        return []
    old, new = resolve(old, old_c), resolve(new, new_c)
    problems: list[str] = []
    if kinds(old, old_c) != kinds(new, new_c) and not (kinds(old, old_c) <= kinds(new, new_c)):
        problems.append(
            f"{path}: the type of {where} changed ({sorted(kinds(old, old_c))} to {sorted(kinds(new, new_c))})"
        )
        return problems
    removed = enum_values(old, old_c) - enum_values(new, new_c)
    if removed and enum_values(old, old_c):
        problems.append(f"{path}: {where} lost the values {sorted(removed)}")
    for name, value in old.get("properties", {}).items():
        label = f"{where}.{name}"
        if name not in new.get("properties", {}):
            problems.append(f"{path}: the response field {label} was removed")
            continue
        problems += compare_response(
            path, value, new["properties"][name], old_c, new_c, label, depth + 1
        )
    if "items" in old and "items" in new:
        problems += compare_response(
            path, old["items"], new["items"], old_c, new_c, where + "[]", depth + 1
        )
    if name_required := set(old.get("required", [])) - set(new.get("required", [])):
        problems.append(
            f"{path}: {where} fields are no longer always present: {sorted(name_required)}"
        )
    return problems


def compare(old: Json, new: Json) -> list[str]:
    """Return the breaking changes between two OpenAPI documents.

    Args:
        old: The old document.
        new: The new document.

    Returns:
        A list of messages. The list is empty when the new document only adds things.
    """
    problems: list[str] = []
    old_c = old.get("components", {}).get("schemas", {})
    new_c = new.get("components", {}).get("schemas", {})
    for path, item in old.get("paths", {}).items():
        for method in HTTP_METHODS:
            if method not in item:
                continue
            label = f"{method.upper()} {path}"
            other = new.get("paths", {}).get(path, {}).get(method)
            if other is None:
                problems.append(f"{label}: the endpoint was removed")
                continue
            before = item[method]
            if before.get("operationId") != other.get("operationId"):
                problems.append(f"{label}: the operationId changed")
            old_params = {(p["in"], p["name"]): p for p in before.get("parameters", [])}
            new_params = {(p["in"], p["name"]): p for p in other.get("parameters", [])}
            for key, param in old_params.items():
                if key not in new_params:
                    problems.append(f"{label}: the parameter {key[1]} was removed")
                    continue
                if not param.get("required") and new_params[key].get("required"):
                    problems.append(f"{label}: the parameter {key[1]} is now required")
                if not kinds(param.get("schema", {}), old_c) <= kinds(
                    new_params[key].get("schema", {}), new_c
                ):
                    problems.append(f"{label}: the type of the parameter {key[1]} changed")
                lost = enum_values(param.get("schema", {}), old_c) - enum_values(
                    new_params[key].get("schema", {}), new_c
                )
                if lost:
                    problems.append(
                        f"{label}: the parameter {key[1]} lost the values {sorted(lost)}"
                    )
                old_max = maximum(param.get("schema", {}))
                new_max = maximum(new_params[key].get("schema", {}))
                if old_max is not None and new_max is not None and new_max < old_max:
                    problems.append(f"{label}: the maximum of {key[1]} went down")
            for key, param in new_params.items():
                if key not in old_params and param.get("required"):
                    problems.append(f"{label}: the new parameter {key[1]} is required")
            for status, response in before.get("responses", {}).items():
                if status not in other.get("responses", {}):
                    problems.append(f"{label}: the response {status} was removed")
                    continue
                old_body = response.get("content", {}).get("application/json", {}).get("schema")
                new_body = (
                    other["responses"][status]
                    .get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )
                if old_body and new_body:
                    problems += compare_response(
                        label + f" ({status})", old_body, new_body, old_c, new_c, "body"
                    )
                elif old_body and not new_body:
                    problems.append(f"{label}: the body of {status} was removed")
    return problems


def main(argv: list[str] | None = None) -> int:
    """Run the check. Return the exit code (0 compatible, 1 breaking, 2 usage error)."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    old = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    new = json.loads(Path(args[1]).read_text(encoding="utf-8"))
    problems = compare(old, new)
    for line in problems:
        print(f"BREAKING: {line}")
    if problems:
        print(
            f"{len(problems)} breaking change(s). Inside v1 the API may only add things.",
            file=sys.stderr,
        )
        return 1
    print("Compatible: the new file only adds things.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
