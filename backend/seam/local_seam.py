from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

_BACKEND = Path(__file__).resolve().parents[1]
_CONTRACTS = _BACKEND / "contracts"


class ContractValidationError(ValueError):
    pass


@dataclass(frozen=True)
class LocalSuccess:
    result: Mapping[str, Any]
    evidence: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class LocalError:
    error_code: str
    error_class: str
    message: str
    details: Mapping[str, Any] | None = None


LocalOutcome = LocalSuccess | LocalError
LocalHandler = Callable[[Mapping[str, Any]], LocalOutcome]


def _load_contract(name: str) -> dict[str, Any]:
    with (_CONTRACTS / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_value(spec: Mapping[str, Any], value: Any, path: str) -> None:
    if value is None:
        if spec.get("nullable", False):
            return
        raise ContractValidationError(f"{path}: null not allowed")

    expected = spec.get("type")
    if expected == "string":
        if not isinstance(value, str):
            raise ContractValidationError(f"{path}: expected string")
        if len(value) < spec.get("min_length", 0):
            raise ContractValidationError(f"{path}: string too short")
        if "max_length" in spec and len(value) > spec["max_length"]:
            raise ContractValidationError(f"{path}: string too long")
    elif expected == "object":
        if not isinstance(value, dict):
            raise ContractValidationError(f"{path}: expected object")
        _validate_object(spec, value, path)
    else:
        raise ContractValidationError(f"{path}: unsupported contract type {expected}")

    if "const" in spec and value != spec["const"]:
        raise ContractValidationError(f"{path}: const mismatch")
    if "enum" in spec and value not in spec["enum"]:
        raise ContractValidationError(f"{path}: enum mismatch")


def _validate_object(contract: Mapping[str, Any], data: Any, path: str = "$") -> None:
    if not isinstance(data, dict):
        raise ContractValidationError(f"{path}: expected object")

    fields = contract.get("fields", {})
    for name in contract.get("required", []):
        if name not in data:
            raise ContractValidationError(f"{path}.{name}: required field missing")

    if contract.get("additional_fields") is False:
        extras = set(data) - set(fields)
        if extras:
            raise ContractValidationError(f"{path}: unexpected fields {sorted(extras)}")

    for name, value in data.items():
        if name in fields:
            _validate_value(fields[name], value, f"{path}.{name}")


def validate_request(request: Mapping[str, Any]) -> None:
    _validate_object(_load_contract("request.v1.json"), request)


def assert_runtime_properties_unresolved() -> None:
    runtime = _load_contract("runtime-properties.v1.json")
    expected = {
        "timeout",
        "retry_backoff",
        "max_attempts",
        "idempotency_behavior",
        "authentication_authorization",
        "protocol_api_schema_compatibility",
    }
    if runtime.get("contract_version") != "1.0":
        raise ContractValidationError("runtime properties: contract version mismatch")
    if set(runtime.get("properties", {})) != expected:
        raise ContractValidationError("runtime properties: property set mismatch")

    allowed_states = set(runtime.get("allowed_states", []))
    for name, prop in runtime["properties"].items():
        if prop.get("state") not in allowed_states:
            raise ContractValidationError(f"runtime property {name}: invalid unresolved state")
        if prop.get("value") is not None or prop.get("evidence_ref") is not None:
            raise ContractValidationError(f"runtime property {name}: unresolved evidence gate violated")


def _identity(request: Mapping[str, Any]) -> dict[str, str]:
    return {
        "contract_version": request["contract_version"],
        "request_id": request["request_id"],
        "task_id": request["task_id"],
        "correlation_id": request["correlation_id"],
    }


def dispatch(request: Mapping[str, Any], handler: LocalHandler) -> dict[str, Any]:
    assert_runtime_properties_unresolved()
    validate_request(request)
    if not callable(handler):
        raise ContractValidationError("handler must be callable")

    request_snapshot = copy.deepcopy(request)
    outcome = handler(request)
    if request != request_snapshot:
        raise ContractValidationError("handler mutated accepted request")

    identity = _identity(request)
    if isinstance(outcome, LocalSuccess):
        if not isinstance(outcome.result, dict):
            raise ContractValidationError("success result must be an object")
        response: dict[str, Any] = {**identity, "status": "SUCCESS", "result": dict(outcome.result)}
        if outcome.evidence is not None:
            if not isinstance(outcome.evidence, dict):
                raise ContractValidationError("success evidence must be an object or null")
            response["evidence"] = dict(outcome.evidence)
        if outcome.metadata is not None:
            if not isinstance(outcome.metadata, dict):
                raise ContractValidationError("success metadata must be an object or null")
            response["metadata"] = dict(outcome.metadata)
        _validate_object(_load_contract("result.v1.json"), response)
        return response

    if isinstance(outcome, LocalError):
        if outcome.error_class not in {"RETRYABLE", "TERMINAL"}:
            raise ContractValidationError("error_class must be RETRYABLE or TERMINAL")
        response = {
            **identity,
            "status": "ERROR",
            "error_code": outcome.error_code,
            "error_class": outcome.error_class,
            "message": outcome.message,
        }
        if outcome.details is not None:
            if not isinstance(outcome.details, dict):
                raise ContractValidationError("error details must be an object or null")
            response["details"] = dict(outcome.details)
        _validate_object(_load_contract("error.v1.json"), response)
        return response

    raise ContractValidationError("handler returned unsupported local outcome")
