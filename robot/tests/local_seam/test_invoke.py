#!/usr/bin/env python3
from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.seam import local_seam as backend_local_seam
from robot.local_seam.invoke import ROBOT_MAX_ATTEMPTS, RobotLocalSeamError, build_backend_request, invoke_local_backend

REQUEST_KWARGS = {
    "request_id": "req-robot-be-001",
    "task_id": "task-robot-be-001",
    "correlation_id": "corr-robot-be-001",
    "operation_id": "op-robot-be-001",
    "operation_type": "fixture.local",
    "payload": {"fixture": True},
    "context": {"source": "robot-local"},
}
IDENTITY = {key: REQUEST_KWARGS[key] for key in ("request_id", "task_id", "correlation_id")}
INVOKE_FILE = ROOT / "robot" / "local_seam" / "invoke.py"
THIS_FILE = Path(__file__)


def success_handler(request):
    assert request["request_id"] == IDENTITY["request_id"]
    assert request["task_id"] == IDENTITY["task_id"]
    assert request["correlation_id"] == IDENTITY["correlation_id"]
    assert request["operation"]["operation_id"] == REQUEST_KWARGS["operation_id"]
    assert request["operation"]["operation_type"] == REQUEST_KWARGS["operation_type"]
    assert request["payload"] == REQUEST_KWARGS["payload"]
    assert request["context"] == REQUEST_KWARGS["context"]
    assert "max_attempts" not in request
    return backend_local_seam.LocalSuccess(result={"accepted": True}, evidence={"mode": "local"})


def retryable_handler(request):
    return backend_local_seam.LocalError("FIXTURE_RETRYABLE", "RETRYABLE", "retry fixture")


def terminal_handler(request):
    return backend_local_seam.LocalError("FIXTURE_TERMINAL", "TERMINAL", "terminal fixture")


def assert_raises(callable_, text):
    try:
        callable_()
    except RobotLocalSeamError as exc:
        assert text in str(exc), (text, str(exc))
    else:
        raise AssertionError(f"expected RobotLocalSeamError containing {text!r}")


def invoke(handler=success_handler, **overrides):
    kwargs = dict(REQUEST_KWARGS)
    kwargs.update(overrides)
    return invoke_local_backend(handler=handler, **kwargs)


def assert_success_retryable_terminal():
    success = invoke()
    assert success["outcome"] == "success"
    assert success["result"] == {"accepted": True}
    assert success["evidence"] == {"mode": "local"}
    assert {key: success[key] for key in IDENTITY} == IDENTITY

    retryable = invoke(retryable_handler)
    assert retryable["outcome"] == "retryable_transient"
    assert retryable["backend_error_class"] == "RETRYABLE"
    assert {key: retryable[key] for key in IDENTITY} == IDENTITY

    terminal = invoke(terminal_handler)
    assert terminal["outcome"] == "terminal"
    assert terminal["backend_error_class"] == "TERMINAL"
    assert {key: terminal[key] for key in IDENTITY} == IDENTITY


def assert_malformed_request_rejected():
    assert_raises(lambda: invoke(request_id=""), "Backend local seam rejected invocation")
    assert_raises(lambda: invoke(payload="not-an-object"), "Backend local seam rejected invocation")


def _base_identity():
    return {"contract_version": "1.0", **IDENTITY}


def assert_malformed_backend_results_rejected():
    malformed_success = {**_base_identity(), "status": "SUCCESS", "result": "not-an-object"}
    with patch("robot.local_seam.invoke.backend_local_seam.dispatch", return_value=malformed_success):
        assert_raises(lambda: invoke(), "result must be an object")

    malformed_error = {
        **_base_identity(),
        "status": "ERROR",
        "error_code": "E",
        "error_class": "TERMINAL",
    }
    with patch("robot.local_seam.invoke.backend_local_seam.dispatch", return_value=malformed_error):
        assert_raises(lambda: invoke(), "malformed Backend ERROR result")

    unknown = {
        **_base_identity(),
        "status": "ERROR",
        "error_code": "E",
        "error_class": "UNKNOWN",
        "message": "unknown",
    }
    with patch("robot.local_seam.invoke.backend_local_seam.dispatch", return_value=unknown):
        assert_raises(lambda: invoke(), "unknown Backend error_class")

    mismatch = {**_base_identity(), "status": "SUCCESS", "result": {}, "request_id": "wrong"}
    with patch("robot.local_seam.invoke.backend_local_seam.dispatch", return_value=mismatch):
        assert_raises(lambda: invoke(), "backend identity mismatch: request_id")


def assert_robot_semantic_isolation():
    request = build_backend_request(**REQUEST_KWARGS)
    assert "max_attempts" not in request
    assert ROBOT_MAX_ATTEMPTS == 3
    assert invoke(retryable_handler)["outcome"] == "retryable_transient"
    assert invoke(terminal_handler)["outcome"] == "terminal"
    backend_local_seam.assert_runtime_properties_unresolved()


def assert_dependency_ceiling():
    banned_imports = {
        "socket",
        "urllib",
        "http",
        "requests",
        "aiohttp",
        "sqlite3",
        "psycopg",
        "psycopg2",
        "sqlalchemy",
        "boto3",
    }
    for path in (INVOKE_FILE, THIS_FILE):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(banned_imports), f"forbidden dependency imported: {sorted(imported & banned_imports)}"

    forbidden_tokens = ("http://", "https://", "database", "storage", "provider", "worker", "queue")
    implementation = INVOKE_FILE.read_text(encoding="utf-8").lower()
    for token in forbidden_tokens:
        assert token not in implementation, f"forbidden implementation token: {token}"


def main():
    assert_success_retryable_terminal()
    assert_malformed_request_rejected()
    assert_malformed_backend_results_rejected()
    assert_robot_semantic_isolation()
    assert_dependency_ceiling()
    print("Robot → Backend local seam tests PASS")


if __name__ == "__main__":
    main()
