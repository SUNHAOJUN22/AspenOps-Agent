from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.registry import NodeRegistry, ResolvedNode

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


class StringFlagBackend(MockBackend):
    def run(self) -> dict[str, Any]:
        return {
            "engine_returned": "false",
            "converged": True,
            "convergence_state": "converged",
        }


class UnsafeDiagnosticBackend(MockBackend):
    def run(self) -> dict[str, Any]:
        return {
            "engine_returned": True,
            "converged": True,
            "convergence_state": "converged",
            "metric": float("nan"),
        }

    def runtime_identity(self) -> dict[str, Any]:
        return {"backend": "mock", "metric": float("inf")}


class FixedReadBackend(MockBackend):
    def __init__(self, key: str, value: float) -> None:
        super().__init__()
        self.key = key
        self.value = value

    def read(self, node: ResolvedNode) -> Any:
        if node.key == self.key:
            return self.value
        return super().read(node)


def empty_request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
        }
    )


def overflow_constraint_request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "constraints": [
                {
                    "name": "overflow_limit",
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": "<=",
                    "value": -1e308,
                    "unit": "fraction",
                }
            ],
        }
    )


def overflow_balance_request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "overflow_balance",
                    "terms": [
                        {
                            "key": "stream.input.mass_flow",
                            "identifiers": {"stream": "FEED"},
                            "coefficient": 1e308,
                            "unit": "kg/h",
                        }
                    ],
                    "expected": 0.0,
                    "abs_tol": 1e-6,
                    "rel_tol": 1e-6,
                }
            ],
        }
    )


def test_backend_boolean_protocol_rejects_truthy_strings() -> None:
    backend = StringFlagBackend()
    backend.open(MODEL)

    result = evaluate(backend, NodeRegistry(REGISTRY), empty_request())

    assert result.communication_ok is True
    assert result.engine_ok is False
    assert "execution_error:TypeError" in result.violations
    assert "must be Boolean" in result.diagnostics["exception"]
    assert not result.ok
    json.dumps(result.to_dict(), allow_nan=False)


def test_backend_diagnostic_non_finite_values_are_sanitized_and_rejected() -> None:
    backend = UnsafeDiagnosticBackend()
    backend.open(MODEL)

    result = evaluate(backend, NodeRegistry(REGISTRY), empty_request())

    assert result.diagnostics["run"]["metric"] is None
    assert result.diagnostics["runtime"]["metric"] is None
    assert result.diagnostics["backend_diagnostic_sanitization"] == {
        "run.metric": "nan",
        "runtime.metric": "positive_infinity",
    }
    assert "backend_diagnostics_not_json_safe" in result.violations
    assert not result.feasible
    json.dumps(result.to_dict(), allow_nan=False)


def test_constraint_derived_overflow_fails_closed_and_stays_json_safe() -> None:
    backend = FixedReadBackend("stream.output.purity", 1e308)
    backend.open(MODEL)

    result = evaluate(backend, NodeRegistry(REGISTRY), overflow_constraint_request())

    assert "constraint_non_finite:overflow_limit" in result.violations
    assert "constraint_failed:overflow_limit" in result.violations
    detail = result.diagnostics["constraints"][0]
    assert detail["actual"] == 1e308
    assert detail["violation"] is None
    assert detail["failure"] == "derived_overflow"
    assert result.diagnostics["total_constraint_violation"] is None
    assert not result.feasible
    json.dumps(result.to_dict(), allow_nan=False)


def test_balance_term_overflow_fails_closed_and_stays_json_safe() -> None:
    backend = FixedReadBackend("stream.input.mass_flow", 1e308)
    backend.open(MODEL)

    result = evaluate(backend, NodeRegistry(REGISTRY), overflow_balance_request())

    assert "balance_non_finite:overflow_balance" in result.violations
    assert "balance_failed:overflow_balance" in result.violations
    assert result.balance_residuals["overflow_balance"]["passed"] == 0.0
    assert result.diagnostics["non_finite_balances"] == {
        "overflow_balance": [
            {
                "identity": "stream.input.mass_flow:stream=FEED",
                "value": "derived_overflow",
            }
        ]
    }
    assert not result.feasible
    json.dumps(result.to_dict(), allow_nan=False)
