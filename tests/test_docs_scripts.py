"""Tests for the documentation scripts (`docs/scripts`)."""

import copy
import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "scripts"))
compat = importlib.import_module("openapi_compat")
OPENAPI = json.loads((ROOT / "docs" / "openapi" / "v1.json").read_text(encoding="utf-8"))


@pytest.fixture
def new():
    return copy.deepcopy(OPENAPI)


def test_same_file_is_compatible(new):
    assert compat.compare(OPENAPI, new) == []


def test_new_endpoint_is_allowed(new):
    new["paths"]["/api/v1/extra"] = copy.deepcopy(new["paths"]["/api/v1/health"])
    assert compat.compare(OPENAPI, new) == []


def test_new_response_field_is_allowed(new):
    new["components"]["schemas"]["Health"]["properties"]["extra"] = {"type": "string"}
    assert compat.compare(OPENAPI, new) == []


def test_removed_endpoint_breaks(new):
    del new["paths"]["/api/v1/health"]
    assert any("endpoint was removed" in line for line in compat.compare(OPENAPI, new))


def test_removed_response_field_breaks(new):
    del new["components"]["schemas"]["Health"]["properties"]["version"]
    assert any("version was removed" in line for line in compat.compare(OPENAPI, new))


def test_changed_field_type_breaks(new):
    new["components"]["schemas"]["Health"]["properties"]["version"] = {"type": "integer"}
    assert any("type of body.version changed" in line for line in compat.compare(OPENAPI, new))


def test_new_required_parameter_breaks(new):
    operation = new["paths"]["/api/v1/reports"]["get"]
    operation["parameters"].append(
        {"name": "x", "in": "query", "required": True, "schema": {"type": "string"}}
    )
    assert any("is required" in line for line in compat.compare(OPENAPI, new))


def test_optional_parameter_made_required_breaks(new):
    new["paths"]["/api/v1/reports"]["get"]["parameters"][0]["required"] = True
    assert any("now required" in line for line in compat.compare(OPENAPI, new))


def test_lower_maximum_breaks(new):
    new["paths"]["/api/v1/reports"]["get"]["parameters"][0]["schema"]["anyOf"][0]["maximum"] = 10
    assert any("maximum of limit went down" in line for line in compat.compare(OPENAPI, new))


def test_removed_status_breaks(new):
    del new["paths"]["/api/v1/me"]["get"]["responses"]["403"]
    assert any("403 was removed" in line for line in compat.compare(OPENAPI, new))


def test_main_exit_codes(tmp_path, new, capsys):
    old_file = tmp_path / "old.json"
    new_file = tmp_path / "new.json"
    old_file.write_text(json.dumps(OPENAPI))
    new_file.write_text(json.dumps(new))
    assert compat.main([str(old_file), str(new_file)]) == 0
    del new["paths"]["/api/v1/health"]
    new_file.write_text(json.dumps(new))
    assert compat.main([str(old_file), str(new_file)]) == 1
    assert "BREAKING" in capsys.readouterr().out
    assert compat.main(["only-one"]) == 2
