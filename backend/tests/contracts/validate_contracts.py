#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
FIXTURES = Path(__file__).with_name("fixtures.v1.json")
SECRET_PATTERNS = [
    re.compile(r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
]


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_value(spec, value, path):
    nullable = spec.get("nullable", False)
    if value is None:
        if nullable:
            return
        raise AssertionError(f"{path}: null not allowed")

    expected = spec.get("type")
    if expected == "string":
        if not isinstance(value, str):
            raise AssertionError(f"{path}: expected string")
        if len(value) < spec.get("min_length", 0):
            raise AssertionError(f"{path}: string too short")
        if "max_length" in spec and len(value) > spec["max_length"]:
            raise AssertionError(f"{path}: string too long")
    elif expected == "object":
        if not isinstance(value, dict):
            raise AssertionError(f"{path}: expected object")
        validate_object(spec, value, path)
    else:
        raise AssertionError(f"{path}: unsupported contract type {expected}")

    if "const" in spec and value != spec["const"]:
        raise AssertionError(f"{path}: const mismatch")
    if "enum" in spec and value not in spec["enum"]:
        raise AssertionError(f"{path}: enum mismatch")


def validate_object(contract, data, path="$"):
    if not isinstance(data, dict):
        raise AssertionError(f"{path}: expected object")
    required = contract.get("required", [])
    fields = contract.get("fields", {})
    for name in required:
        if name not in data:
            raise AssertionError(f"{path}.{name}: required field missing")
    if contract.get("additional_fields") is False:
        extras = set(data) - set(fields)
        if extras:
            raise AssertionError(f"{path}: unexpected fields {sorted(extras)}")
    for name, value in data.items():
        if name in fields:
            validate_value(fields[name], value, f"{path}.{name}")


def assert_round_trip(fixtures):
    expected = fixtures["correlation_round_trip"]
    for name in ("valid_request", "valid_success_result", "retryable_error", "terminal_error"):
        actual = {key: fixtures[name][key] for key in expected}
        assert actual == expected, f"{name}: correlation identity mismatch"


def assert_runtime_gates(runtime_contract):
    assert runtime_contract["contract_version"] == "1.0"
    allowed = set(runtime_contract["allowed_states"])
    expected = {
        "timeout", "retry_backoff", "max_attempts", "idempotency_behavior",
        "authentication_authorization", "protocol_api_schema_compatibility",
    }
    assert set(runtime_contract["properties"]) == expected
    for name, prop in runtime_contract["properties"].items():
        assert prop["state"] in allowed, f"{name}: invalid unresolved state"
        assert prop["value"] is None, f"{name}: guessed runtime default present"
        assert prop["evidence_ref"] is None, f"{name}: unevidenced reference present"


def assert_no_secrets(paths):
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(text), f"secret-like material in {path}"


def main():
    request = load_json(CONTRACTS / "request.v1.json")
    result = load_json(CONTRACTS / "result.v1.json")
    error = load_json(CONTRACTS / "error.v1.json")
    runtime = load_json(CONTRACTS / "runtime-properties.v1.json")
    fixtures = load_json(FIXTURES)

    assert request["contract_version"] == result["contract_version"] == error["contract_version"] == "1.0"
    validate_object(request, fixtures["valid_request"])
    validate_object(result, fixtures["valid_success_result"])
    validate_object(error, fixtures["retryable_error"])
    validate_object(error, fixtures["terminal_error"])
    assert fixtures["retryable_error"]["error_class"] == "RETRYABLE"
    assert fixtures["terminal_error"]["error_class"] == "TERMINAL"
    assert fixtures["retryable_error"]["error_class"] != fixtures["terminal_error"]["error_class"]

    rejected = False
    try:
        validate_object(request, fixtures["invalid_missing_required"])
    except AssertionError:
        rejected = True
    assert rejected, "invalid fixture was not rejected"

    assert_round_trip(fixtures)
    assert_runtime_gates(runtime)
    paths = list(CONTRACTS.glob("*.json")) + [FIXTURES, Path(__file__)]
    assert_no_secrets(paths)
    print("Backend contract tests PASS")


if __name__ == "__main__":
    main()
