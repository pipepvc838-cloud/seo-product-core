#!/usr/bin/env python3
import ast
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.seam.local_seam import ContractValidationError, LocalError, LocalSuccess, assert_runtime_properties_unresolved, dispatch

CONTRACTS = ROOT / "backend" / "contracts"
SEAM_FILE = ROOT / "backend" / "seam" / "local_seam.py"
THIS_FILE = Path(__file__)

REQUEST = {
    "contract_version": "1.0",
    "request_id": "req-seam-001",
    "task_id": "task-seam-001",
    "correlation_id": "corr-seam-001",
    "operation": {"operation_id": "op-seam-001", "operation_type": "fixture.local"},
    "payload": {"fixture": True},
}
IDENTITY = {key: REQUEST[key] for key in ("contract_version", "request_id", "task_id", "correlation_id")}


def load_contract(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def validate_value(spec, value, path):
    if value is None:
        assert spec.get("nullable", False), f"{path}: null not allowed"
        return
    expected = spec.get("type")
    if expected == "string":
        assert isinstance(value, str), f"{path}: expected string"
        assert len(value) >= spec.get("min_length", 0), f"{path}: string too short"
        if "max_length" in spec:
            assert len(value) <= spec["max_length"], f"{path}: string too long"
    elif expected == "object":
        assert isinstance(value, dict), f"{path}: expected object"
        validate_object(spec, value, path)
    else:
        raise AssertionError(f"{path}: unsupported type")
    if "const" in spec:
        assert value == spec["const"], f"{path}: const mismatch"
    if "enum" in spec:
        assert value in spec["enum"], f"{path}: enum mismatch"


def validate_object(contract, data, path="$"):
    assert isinstance(data, dict), f"{path}: expected object"
    fields = contract.get("fields", {})
    for name in contract.get("required", []):
        assert name in data, f"{path}.{name}: required field missing"
    if contract.get("additional_fields") is False:
        assert not (set(data) - set(fields)), f"{path}: unexpected fields"
    for name, value in data.items():
        if name in fields:
            validate_value(fields[name], value, f"{path}.{name}")


def success_handler(request):
    assert request is REQUEST
    return LocalSuccess(result={"accepted": True}, evidence={"source": "fixed-fixture"})


def terminal_handler(request):
    assert request is REQUEST
    return LocalError("FIXTURE_TERMINAL", "TERMINAL", "Deterministic terminal fixture", {"fixture": True})


def retryable_handler(request):
    assert request is REQUEST
    return LocalError("FIXTURE_RETRYABLE", "RETRYABLE", "Deterministic retryable fixture")


def assert_identity(value):
    assert {key: value[key] for key in IDENTITY} == IDENTITY


def assert_invalid_rejected():
    invalid = copy.deepcopy(REQUEST)
    invalid.pop("payload")
    try:
        dispatch(invalid, success_handler)
    except ContractValidationError:
        pass
    else:
        raise AssertionError("missing required field was accepted")

    extra = copy.deepcopy(REQUEST)
    extra["unexpected"] = True
    try:
        dispatch(extra, success_handler)
    except ContractValidationError:
        pass
    else:
        raise AssertionError("forbidden additional field was accepted")


def assert_dependency_ceiling():
    tree = ast.parse(SEAM_FILE.read_text(encoding="utf-8"))
    banned = {"socket", "urllib", "http", "requests", "aiohttp", "sqlite3", "psycopg", "psycopg2", "sqlalchemy"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(banned), f"forbidden dependency imported: {sorted(imported & banned)}"


def assert_no_secret_patterns():
    patterns = [
        re.compile(r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    ]
    for path in (SEAM_FILE, THIS_FILE):
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            assert not pattern.search(text), f"secret-like material in {path}"


def main():
    before = copy.deepcopy(REQUEST)
    success = dispatch(REQUEST, success_handler)
    assert success["status"] == "SUCCESS"
    assert_identity(success)
    validate_object(load_contract("result.v1.json"), success)

    terminal = dispatch(REQUEST, terminal_handler)
    assert terminal["status"] == "ERROR" and terminal["error_class"] == "TERMINAL"
    assert_identity(terminal)
    validate_object(load_contract("error.v1.json"), terminal)

    retryable = dispatch(REQUEST, retryable_handler)
    assert retryable["status"] == "ERROR" and retryable["error_class"] == "RETRYABLE"
    assert retryable["error_class"] != terminal["error_class"]
    assert_identity(retryable)
    validate_object(load_contract("error.v1.json"), retryable)

    assert REQUEST == before
    assert_invalid_rejected()
    assert_runtime_properties_unresolved()
    assert_dependency_ceiling()
    assert_no_secret_patterns()
    print("Backend runtime seam tests PASS")


if __name__ == "__main__":
    main()
