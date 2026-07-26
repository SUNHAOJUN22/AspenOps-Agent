from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

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


class ConvergedStringBackend(MockBackend):
    def run(self) -> dict[str, Any]:
        return {
            "engine_returned": True,
            "converged": "true",
            "convergence_state": "converged",
        }


class InvalidStateBackend(MockBackend):
    def run(self) -> dict[str, Any]:
        return {
            "engine_returned": True,
            "converged": True,
            "convergence_state": None,
        }


class InvalidShapeBackend(MockBackend):
    def run(self) -> dict[str, Any]:
        return []  # type: ignore[return-value]


class InvalidRuntimeBackend(MockBackend):
    def runtime_identity(self) -> dict[str, Any]:
        return []  # type: ignore[return-value]


class UnsafeDiagnosticBackend(MockBackend):
    def run(self) -> dict[str, Any]:
        return {
            "engine_returned": True,
            "converged": True,
            "convergence_state": "converged",
            "metric": float("nan"),
            "nested": (1.0, Path("diagnostic-path")),
        }

    def runtime_identity(self) -> dict[str, Any]:
        return {
            "backend": "mock",
            "metric": float("inf"),
            "opaque": object(),
        }


class FixedReadBackend(MockBackend):
    def __init__(self, key: str, value: Any) -> None:
        super().__init__()
        self.key = key
        self.value = value

    def read(self, node: ResolvedNode) -> Any:
        if node.key == self.key:
            return self.value
        return super().read(node)


class MappingReadBackend(MockBackend):
    def __init__(self, values: dict[str, Any]) -> None:
        super().__init__()
        self.values = values

    def read(self, node: ResolvedNode) -> Any:
        if node.key in self.values:
            return self.values[node.key]
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


def constraint_request(*, name: str = "overflow_limit", limit: float = -1e308) -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "constraints": [
                {
                    "name": name,
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": "<=",
                    "value": limit,
                    "unit": "fraction",
                }
            ],
        }
    )


def balance_request(
    *,
    name: str = "overflow_balance",
    coefficient: float = 1e308,
    include_product: bool = False,
) -> EvaluationRequest:
    terms: list[dict[str, object]] = [
        {
            "key": "stream.input.mass_flow",
            "identifiers": {"stream": "FEED"},
            "coefficient": coefficient,
            "unit": "kg/h",
        }
    ]
    if include_product:
        terms.append(
            {
                "key": "stream.output.mass_flow",
                "identifiers": {"stream": "PRODUCT"},
                "coefficient": coefficient,
                "unit": "kg/h",
            }
        )
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": name,
                    "terms": terms,
                    "expected": 0.0,
                    "abs_tol": 1e-6,
                    "rel_tol": 1e-6,
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "backend",
    [StringFlagBackend(), ConvergedStringBackend(), InvalidStateBackend()],
)
def test_backend_run_protocol_rejects_ambiguous_fields(backend: MockBackend) -> None:
    backend.open(MODEL)

    result = evaluate(backend, NodeRegistry(REGISTRY), empty_request())

    assert result.communication_ok is True
    assert result.engine_ok is False
    assert "execution_error:TypeError" in result.violations
    assert not result.ok
    json.dumps(result.to_dict(), allow_nan=False)


def test_backend_run_and_runtime_shapes_must_be_objects() -> None:
    run_backend = InvalidShapeBackend()
    run_backend.open(MODEL)
    run_result = evaluate(run_backend, NodeRegistry(REGISTRY), empty_request())
    assert "execution_error:TypeError" in run_result.violations

    runtime_backend = InvalidRuntimeBackend()
    runtime_backend.open(MODEL)
    runtime_result = evaluate(runtime_backend, NodeRegistry(REGISTRY), empty_request())
    assert runtime_result.engine_ok is True
    assert "execution_error:TypeError" in runtime_result.violations

    json.dumps(run_result.to_dict(), allow_nan=False)
    json.dumps(runtime_result.to_dict(), allow_nan=False)


def test_backend_diagnostics_are_sanitized_and_rejected() -> None:
    backend = UnsafeDiagnosticBackend()
    backend.open(MODEL)

    result = evaluate(backend, NodeRegistry(REGISTRY), empty_request())

    assert result.diagnostics["run"]["metric"] is None
    assert result.diagnostics["run"]["nested"] == [1.0, "diagnostic-path"]
    assert result.diagnostics["runtime"]["metric"] is None
    assert result.diagnostics["backend_diagnostic_sanitization"]["run.metric"] == "nan"
    assert (
        result.diagnostics["backend_diagnostic_sanitization"]["runtime.metric"]
        == "positive_infinity"
    )
    assert result.diagnostics["backend_diagnostic_sanitization"]["runtime.opaque"].startswith(
        "unsupported_type:object"
    )
    assert "backend_diagnostics_not_json_safe" in result.violations
    assert not result.feasible
    json.dumps(result.to_dict(), allow_nan=False)


def test_constraint_derived_overflow_fails_closed_and_stays_json_safe() -> None:
    backend = FixedReadBackend("stream.output.purity", 1e308)
    backend.open(MODEL)

    result = evaluate(backend, NodeRegistry(REGISTRY), constraint_request())

    assert "constraint_non_finite:overflow_limit" in result.violations
    assert "constraint_failed:overflow_limit" in result.violations
    detail = result.diagnostics["constraints"][0]
    assert detail["actual"] == 1e308
    assert detail["violation"] is None
    assert detail["failure"] == "derived_overflow"
    assert result.diagnostics["total_constraint_violation"] is None
    assert not result.feasible
    json.dumps(result.to_dict(), allow_nan=False)


def test_non_numeric_constraint_fails_closed_and_stays_json_safe() -> None:
    backend = FixedReadBackend("stream.output.purity", "not-a-number")
    backend.open(MODEL)

    result = evaluate(
        backend,
        NodeRegistry(REGISTRY),
        constraint_request(name="text_constraint", limit=0.5),
    )

    assert "constraint_non_numeric:text_constraint" in result.violations
    assert "constraint_failed:text_constraint" in result.violations
    assert result.diagnostics["constraints"][0]["observed_type"] == "str"
    assert not result.feasible
    json.dumps(result.to_dict(), allow_nan=False)


def test_balance_term_overflow_fails_closed_and_stays_json_safe() -> None:
    backend = FixedReadBackend("stream.input.mass_flow", 1e308)
    backend.open(MODEL)

    result = evaluate(backend, NodeRegistry(REGISTRY), balance_request())

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


def test_non_numeric_balance_term_fails_closed_and_stays_json_safe() -> None:
    backend = FixedReadBackend("stream.input.mass_flow", "invalid")
    backend.open(MODEL)

    result = evaluate(
        backend,
        NodeRegistry(REGISTRY),
        balance_request(name="text_balance", coefficient=1.0),
    )

    assert "balance_non_finite:text_balance" in result.violations
    assert result.diagnostics["non_finite_balances"]["text_balance"][0]["value"] == (
        "non_numeric:str"
    )
    json.dumps(result.to_dict(), allow_nan=False)


def test_balance_sum_overflow_uses_structured_failure() -> None:
    backend = MappingReadBackend(
        {
            "stream.input.mass_flow": 1e308,
            "stream.output.mass_flow": 1e308,
        }
    )
    backend.open(MODEL)

    result = evaluate(
        backend,
        NodeRegistry(REGISTRY),
        balance_request(name="sum_overflow", coefficient=1.0, include_product=True),
    )

    assert "balance_non_finite:sum_overflow" in result.violations
    assert result.diagnostics["non_finite_balances"]["sum_overflow"] == [
        {"identity": "derived_balance", "value": "derived_overflow"}
    ]
    assert "execution_error:OverflowError" not in result.violations
    json.dumps(result.to_dict(), allow_nan=False)
