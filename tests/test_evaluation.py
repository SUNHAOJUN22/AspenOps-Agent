import math
from pathlib import Path

import pytest

from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.optimization import _Evaluator
from aspenops_nexus.registry import NodeRegistry

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def test_constraints_and_balances_are_enforced() -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [
                {
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "value": 100,
                    "unit": "C",
                }
            ],
            "reads": [],
            "constraints": [
                {
                    "name": "minimum_conversion",
                    "key": "reactor.output.conversion",
                    "identifiers": {"block": "R1"},
                    "operator": ">=",
                    "value": 0.5,
                    "unit": "fraction",
                }
            ],
            "balances": [
                {
                    "name": "deliberately_strict_mass_balance",
                    "terms": [
                        {
                            "key": "stream.input.mass_flow",
                            "identifiers": {"stream": "FEED"},
                            "coefficient": 1,
                            "unit": "kg/h",
                        },
                        {
                            "key": "stream.output.mass_flow",
                            "identifiers": {"stream": "PRODUCT"},
                            "coefficient": -1,
                            "unit": "kg/h",
                        },
                    ],
                    "abs_tol": 0.01,
                    "rel_tol": 0.0001,
                }
            ],
        }
    )
    backend = MockBackend()
    backend.open(MODEL)
    result = evaluate(backend, NodeRegistry(REGISTRY), request)
    backend.close()

    assert result.communication_ok
    assert result.converged
    assert not result.feasible
    assert "balance_failed:deliberately_strict_mass_balance" in result.violations
    assert result.diagnostics["constraints"][0]["passed"] is True
    assert result.balance_residuals["deliberately_strict_mass_balance"]["relative"] > 0


def test_constraint_failure_is_named() -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "constraints": [
                {
                    "name": "impossible_purity",
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": ">=",
                    "value": 0.99999,
                    "unit": "fraction",
                }
            ],
        }
    )
    backend = MockBackend()
    backend.open(MODEL)
    result = evaluate(backend, NodeRegistry(REGISTRY), request)
    backend.close()

    assert not result.ok
    assert "constraint_failed:impossible_purity" in result.violations


def test_constraint_tolerance_is_applied() -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "constraints": [
                {
                    "name": "purity_with_tolerance",
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": "==",
                    "value": 0.8685,
                    "tolerance": 0.001,
                    "unit": "fraction",
                }
            ],
        }
    )
    backend = MockBackend()
    backend.open(MODEL)
    result = evaluate(backend, NodeRegistry(REGISTRY), request)
    backend.close()
    assert result.ok
    assert result.engine_ok
    assert result.diagnostics["state_trace"][-1] == "verified"


@pytest.mark.parametrize("operator", ["<", "<=", ">", ">="])
@pytest.mark.parametrize("tolerance", [0.0, 0.125])
@pytest.mark.parametrize("side", [-1, 0, 1])
def test_strict_constraint_boundary_and_optimizer_admission(
    operator: str, tolerance: float, side: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    limit = 1.0
    threshold = limit + (tolerance if operator in {">", "<="} else -tolerance)
    actual = threshold
    if side != 0:
        actual = math.nextafter(threshold, math.copysign(math.inf, side))
    if operator in {"<", ">"}:
        expected = side == (-1 if operator == "<" else 1)
    else:
        expected = side != (1 if operator == "<=" else -1)
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "constraints": [
                {
                    "name": "boundary",
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": operator,
                    "value": limit,
                    "tolerance": tolerance,
                    "unit": "fraction",
                }
            ],
        }
    )
    backend = MockBackend()
    backend.open(MODEL)
    monkeypatch.setattr(backend, "bulk_read", lambda nodes: [actual] * len(nodes))
    try:
        result = evaluate(backend, NodeRegistry(REGISTRY), request)
    finally:
        backend.close()
    assert result.communication_ok and result.engine_ok and result.converged
    assert result.ok is expected
    assert result.feasible is expected
    detail = result.diagnostics["constraints"][0]
    assert detail["passed"] is expected
    assert ("constraint_failed:boundary" in result.violations) is not expected
    # The continuous distance is zero at the boundary, even for an open set.
    if side == 0:
        assert detail["violation"] == 0.0
        assert result.diagnostics["total_constraint_violation"] == 0.0
    score = _Evaluator._violation(result.to_dict())
    assert (score == 0.0) is expected
    assert math.isfinite(score)
