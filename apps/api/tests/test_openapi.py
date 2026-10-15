"""The committed OpenAPI file must match the code, and every operation must be documented."""

import json
from pathlib import Path

import pytest

from apps.api.management.commands.export_openapi import render

ROOT = Path(__file__).resolve().parents[3]
COMMITTED = ROOT / "docs" / "openapi" / "v1.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture(scope="module")
def schema():
    return json.loads(render("v1"))


def test_committed_file_is_current():
    assert COMMITTED.read_text(encoding="utf-8") == render("v1"), (
        "docs/openapi/v1.json is out of date. Run: "
        "python manage.py export_openapi --output docs/openapi/v1.json"
    )


def test_export_is_stable():
    assert render("v1") == render("v1")


def test_every_operation_is_documented(schema):
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method not in HTTP_METHODS:
                continue
            where = f"{method.upper()} {path}"
            assert operation.get("operationId"), where
            assert operation.get("summary"), where
            assert operation.get("description"), where
            assert operation.get("tags"), where


def test_operation_ids_are_unique(schema):
    ids = [
        op["operationId"]
        for item in schema["paths"].values()
        for method, op in item.items()
        if method in HTTP_METHODS
    ]
    assert len(ids) == len(set(ids))


def test_protected_operations_document_the_error_answers(schema):
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method not in HTTP_METHODS or path.endswith("/health"):
                continue
            assert {"401", "403", "429"} <= set(operation["responses"]), f"{method} {path}"


def test_detail_operations_document_404(schema):
    for path in ("/api/v1/reports/{day}", "/api/v1/ipos/{ipo_id}"):
        assert "404" in schema["paths"][path]["get"]["responses"]


def test_security_schemes_exist(schema):
    assert {"BearerToken", "SessionCookie"} <= set(schema["components"]["securitySchemes"])


def test_every_schema_property_has_a_description(schema):
    missing = [
        f"{name}.{prop}"
        for name, body in schema["components"]["schemas"].items()
        for prop, value in body.get("properties", {}).items()
        if not (value.get("description") or value.get("$ref") or value.get("allOf"))
    ]
    assert not missing, missing[:20]
