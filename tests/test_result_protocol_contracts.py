from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.worker import WorkerHandle, evaluate_on_worker


class Process:
    def is_alive(self) -> bool:
        return True


class Connection:
    def __init__(self, result_payload: dict[str, Any]) -> None:
        self.result_payload = result_payload
        self.request_id = ""

    def send(self, command: dict[str, Any]) -> None:
        self.request_id = str(command["request_id"])

    def poll(self, timeout: float = 0.0) -> bool:
        del timeout
        return True

    def recv(self) -> dict[str, Any]:
        return {
            "protocol": 1,
            "kind": "result",
            "request_id": self.request_id,
            "result": self.result_payload,
        }

    def close(self) -> None:
        return None


def valid_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "communication_ok": True,
        "engine_ok": True,
        "converged": True,
        "feasible": True,
        "values": {"x": 1.0},
        "units": {"x": None},
        "violations": [],
        "diagnostics": {},
        "elapsed_s": 0.1,
        "balance_residuals": {},
    }


def request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": "model.json",
            "registry_path": "registry.json",
            "timeout_s": 1.0,
        }
    )


def handle(payload: dict[str, Any]) -> WorkerHandle:
    return WorkerHandle(
        worker_id=0,
        process=Process(),
        connection=Connection(payload),
        staged_model=Path("model.json"),
        runtime={},
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ok", 1),
        ("communication_ok", "true"),
        ("converged", None),
        ("feasible", []),
        ("values", []),
        ("units", []),
        ("violations", "none"),
        ("diagnostics", []),
        ("balance_residuals", []),
        ("elapsed_s", float("nan")),
        ("cache_source", "unknown"),
        ("cache_hit", 1),
        ("request_hash", []),
        ("worker_id", True),
    ],
)
def test_malformed_result_fields_become_protocol_error(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value
    result = evaluate_on_worker(handle(payload), request())
    assert result.violations == ["worker_protocol_error"]
    assert "invalid result payload" in result.diagnostics["detail"]


def test_result_elapsed_must_be_finite_non_negative() -> None:
    for value in (-1.0, float("inf"), float("nan"), True):
        payload = valid_payload()
        payload["elapsed_s"] = value
        with pytest.raises(ValueError, match="elapsed_s must be a finite non-negative number"):
            EvaluationResult.from_dict(payload)


def test_legacy_result_without_engine_ok_remains_compatible() -> None:
    payload = valid_payload()
    payload.pop("engine_ok")
    result = EvaluationResult.from_dict(payload)
    assert result.engine_ok is True
    assert math.isfinite(result.elapsed_s)


def test_valid_result_round_trip_preserves_cache_fields() -> None:
    payload = valid_payload()
    payload.update(
        {
            "cache_source": "persistent_cache",
            "cache_hit": True,
            "request_hash": "abc",
            "worker_id": 2,
        }
    )
    result = EvaluationResult.from_dict(payload)
    assert EvaluationResult.from_dict(result.to_dict()).to_dict() == result.to_dict()
