#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
EXTERNAL = CONTRACTS / "external-invocation.v1.json"

UNRESOLVED = {
    "transport_protocol",
    "authentication_mapping",
    "timeout",
    "retry_backoff",
    "backend_max_attempts",
    "idempotency_behavior",
    "protocol_api_schema_compatibility",
    "transport_error_mapping_details",
}
FORBIDDEN_PROVIDER_TERMS = {"openai", "anthropic", "google", "azure", "aws"}
FORBIDDEN_TRANSPORT_VALUES = {"http", "https", "rest", "grpc", "webhook", "queue"}
SECRET_PATTERNS = [
    re.compile(r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
]


def load(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    external = load(EXTERNAL)
    request = load(CONTRACTS / "request.v1.json")
    result = load(CONTRACTS / "result.v1.json")
    error = load(CONTRACTS / "error.v1.json")

    assert external["contract_version"] == "1.0"
    boundary = external["boundary"]
    assert boundary["owner"] == "Backend"
    assert boundary["operations_governance_owner"] == "Operations"
    assert boundary["provider_neutral"] is True
    assert set(boundary["excluded_provider_transport_owners"]) == {"Robot", "WordPress", "Intelligence"}

    envelopes = external["envelopes"]
    assert envelopes == {
        "request_contract": "backend/contracts/request.v1.json",
        "result_contract": "backend/contracts/result.v1.json",
        "error_contract": "backend/contracts/error.v1.json",
        "reuse_rule": "Accepted Backend envelope semantics are referenced and MUST NOT be redefined here.",
    }

    assert request["contract_version"] == result["contract_version"] == error["contract_version"] == "1.0"
    assert request["required"] == ["contract_version", "request_id", "task_id", "correlation_id", "operation", "payload"]
    assert result["required"] == ["contract_version", "request_id", "task_id", "correlation_id", "status", "result"]
    assert error["required"] == ["contract_version", "request_id", "task_id", "correlation_id", "status", "error_code", "error_class", "message"]
    assert result["fields"]["status"]["enum"] == ["SUCCESS"]
    assert error["fields"]["status"]["enum"] == ["ERROR"]
    assert error["fields"]["error_class"]["enum"] == ["RETRYABLE", "TERMINAL"]

    identity = external["identity_preservation"]
    assert identity["required"] == ["request_id", "task_id", "correlation_id"]
    for name in identity["required"]:
        assert name in request["fields"] and name in result["fields"] and name in error["fields"]

    unresolved = external["unresolved_properties"]
    assert set(unresolved) == UNRESOLVED
    for name, spec in unresolved.items():
        assert spec["state"] == "EVIDENCE_REQUIRED", name
        assert spec["value"] is None, name

    assert external["implementation"] == {"authorized": False, "external_io": False}

    text = EXTERNAL.read_text(encoding="utf-8")
    lowered = text.lower()
    for provider in FORBIDDEN_PROVIDER_TERMS:
        assert provider not in lowered, f"provider-specific reference: {provider}"
    for value in FORBIDDEN_TRANSPORT_VALUES:
        assert f'\"value\": \"{value}\"' not in lowered, f"concrete transport selected: {value}"
    for pattern in SECRET_PATTERNS:
        assert not pattern.search(text), "secret-like material detected"

    print("External invocation contract tests PASS")


if __name__ == "__main__":
    main()
