from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any, Callable

from backend.seam import local_seam as backend_local_seam

ROBOT_MAX_ATTEMPTS = 3


class RobotLocalSeamError(ValueError):
    """Fail-closed Robot-local seam validation error."""


def build_backend_request(
    *,
    request_id: str,
    task_id: str,
    correlation_id: str,
    operation_id: str,
    operation_type: str,
    payload: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
    contract_version: str = "1.0",
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "contract_version": contract_version,
        "request_id": request_id,
        "task_id": task_id,
        "correlation_id": correlation_id,
        "operation": {
            "operation_id": operation_id,
            "operation_type": operation_type,
        },
        "payload": dict(payload) if isinstance(payload, Mapping) else payload,
    }
    if context is not None:
        request["context"] = dict(context) if isinstance(context, Mapping) else context
    return request


def _identity(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": request.get("contract_version"),
        "request_id": request.get("request_id"),
        "task_id": request.get("task_id"),
        "correlation_id": request.get("correlation_id"),
    }


def _require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RobotLocalSeamError(f"{field} must be an object")
    return value


def _validate_backend_response(response: Any, expected_identity: Mapping[str, Any]) -> dict[str, Any]:
    data = _require_object(response, "backend response")
    for key, expected in expected_identity.items():
        if data.get(key) != expected:
            raise RobotLocalSeamError(f"backend identity mismatch: {key}")

    status = data.get("status")
    if status == "SUCCESS":
        required = {"contract_version", "request_id", "task_id", "correlation_id", "status", "result"}
        allowed = required | {"evidence", "metadata"}
        if not required.issubset(data) or set(data) - allowed:
            raise RobotLocalSeamError("malformed Backend SUCCESS result")
        _require_object(data["result"], "result")
        if "evidence" in data:
            _require_object(data["evidence"], "evidence")
        if "metadata" in data:
            _require_object(data["metadata"], "metadata")
        return data

    if status == "ERROR":
        required = {
            "contract_version",
            "request_id",
            "task_id",
            "correlation_id",
            "status",
            "error_code",
            "error_class",
            "message",
        }
        allowed = required | {"details"}
        if not required.issubset(data) or set(data) - allowed:
            raise RobotLocalSeamError("malformed Backend ERROR result")
        if not all(isinstance(data[name], str) and data[name] for name in ("error_code", "error_class", "message")):
            raise RobotLocalSeamError("malformed Backend ERROR fields")
        if data["error_class"] not in {"RETRYABLE", "TERMINAL"}:
            raise RobotLocalSeamError("unknown Backend error_class")
        if "details" in data:
            _require_object(data["details"], "details")
        return data

    raise RobotLocalSeamError("unsupported Backend response status")


def invoke_local_backend(
    *,
    handler: Callable[[Mapping[str, Any]], Any],
    request_id: str,
    task_id: str,
    correlation_id: str,
    operation_id: str,
    operation_type: str,
    payload: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request = build_backend_request(
        request_id=request_id,
        task_id=task_id,
        correlation_id=correlation_id,
        operation_id=operation_id,
        operation_type=operation_type,
        payload=payload,
        context=context,
    )
    request_snapshot = copy.deepcopy(request)
    expected_identity = _identity(request)

    try:
        response = backend_local_seam.dispatch(request, handler)
    except backend_local_seam.ContractValidationError as exc:
        raise RobotLocalSeamError(f"Backend local seam rejected invocation: {exc}") from exc

    if request != request_snapshot:
        raise RobotLocalSeamError("Backend local invocation mutated Robot request")

    data = _validate_backend_response(response, expected_identity)
    identity = {key: data[key] for key in ("request_id", "task_id", "correlation_id")}

    if data["status"] == "SUCCESS":
        mapped: dict[str, Any] = {**identity, "outcome": "success", "result": copy.deepcopy(data["result"])}
        if "evidence" in data:
            mapped["evidence"] = copy.deepcopy(data["evidence"])
        if "metadata" in data:
            mapped["metadata"] = copy.deepcopy(data["metadata"])
        return mapped

    error = {
        "error_code": data["error_code"],
        "message": data["message"],
    }
    if "details" in data:
        error["details"] = copy.deepcopy(data["details"])

    if data["error_class"] == "RETRYABLE":
        return {**identity, "outcome": "retryable_transient", "backend_error_class": "RETRYABLE", "error": error}
    if data["error_class"] == "TERMINAL":
        return {**identity, "outcome": "terminal", "backend_error_class": "TERMINAL", "error": error}

    raise RobotLocalSeamError("unknown Backend error_class")
