from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus import RUNTIME_SCHEMA, __version__
from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.hashing import canonical_hash
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.optimization import _Evaluator
from aspenops_nexus.pool import CasePool
from aspenops_nexus.registry import NodeRegistry, ResolvedNode

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


class PrescribedFlowBackend(MockBackend):
    def __init__(self, values: tuple[float, ...]) -> None:
        super().__init__()
        self.values = values

    def read(self, node: ResolvedNode) -> Any:
        if node.key == "stream.input.mass_flow":
            return self.values[int(node.identifiers["stream"])]
        return super().read(node)


def balance_request(
    values: tuple[float, ...], *, expected: float, abs_tol: float = 0.0, rel_tol: float = 0.0
) -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "mass",
                    "base_unit": "kg/h",
                    "terms": [
                        {
                            "key": "stream.input.mass_flow",
                            "identifiers": {"stream": str(index)},
                            "coefficient": 1.0,
                            "unit": "kg/h",
                        }
                        for index in range(len(values))
                    ],
                    "expected": expected,
                    "abs_tol": abs_tol,
                    "rel_tol": rel_tol,
                    "floor": 1.0,
                }
            ],
        }
    )


def evaluate_flows(values: tuple[float, ...], request: EvaluationRequest) -> EvaluationResult:
    backend = PrescribedFlowBackend(values)
    backend.open(MODEL)
    try:
        result = evaluate(backend, NodeRegistry(REGISTRY), request)
    finally:
        backend.close()
    return EvaluationResult.from_dict(json.loads(json.dumps(result.to_dict(), allow_nan=False)))


@pytest.mark.parametrize("large", [1e16, -1e16, 1e100, -1e100])
@pytest.mark.parametrize("small", [1.0, -1.0])
@pytest.mark.parametrize("reverse", [False, True])
def test_target_cancellation_preserves_representable_nonzero_residual(
    large: float, small: float, reverse: bool
) -> None:
    values = (small, large) if reverse else (large, small)
    exact_residual = sum(map(Fraction.from_float, values)) - Fraction.from_float(large)
    assert exact_residual == Fraction.from_float(small)
    # The intermediate subtotal rounds the small flow away before target subtraction.
    assert math.fsum(values) - large == 0.0

    result = evaluate_flows(values, balance_request(values, expected=large))
    detail = result.balance_residuals["mass"]
    assert result.communication_ok and result.engine_ok and result.converged
    assert not result.ok
    assert not result.feasible
    assert detail["residual"] == float(exact_residual)
    assert detail["relative"] > 0.0
    assert detail["status"] == "fail"
    assert "balance_failed:mass" in result.violations
    assert _Evaluator._violation(result.to_dict()) > 0.0


@pytest.mark.parametrize(
    "abs_tol,rel_tol,passed",
    [(0.5, 0.0, False), (1.0, 0.0, True), (0.0, 1e-16, True)],
)
def test_compensated_residual_still_obeys_absolute_or_relative_tolerance(
    abs_tol: float, rel_tol: float, passed: bool
) -> None:
    values = (1e16, 1.0)
    result = evaluate_flows(
        values, balance_request(values, expected=1e16, abs_tol=abs_tol, rel_tol=rel_tol)
    )
    assert result.balance_residuals["mass"]["residual"] == 1.0
    assert result.balance_residuals["mass"]["passed"] is passed
    assert result.ok is passed


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_exact_cancellation_with_nonzero_target_remains_accepted(sign: float) -> None:
    values = tuple(sign * value for value in (1e16, 1.0, 2.0, -3.0))
    target = sign * 1e16
    assert sum(map(Fraction.from_float, values)) - Fraction.from_float(target) == 0
    result = evaluate_flows(values, balance_request(values, expected=target))
    assert result.ok
    assert result.balance_residuals["mass"]["residual"] == 0.0


def test_residual_fix_cannot_replay_underflow_v1_cache(tmp_path: Path) -> None:
    request = balance_request((1e16, 1.0), expected=1e16)
    pool = CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )
    previous_key = canonical_hash(
        {
            "schema": RUNTIME_SCHEMA,
            "runtime_version": __version__,
            "backend": pool.backend_name,
            "runtime_identity": pool._runtime_cache_identity(),
            "model_sha256": pool.model_sha256,
            "registry_sha256": pool._registry_digest(),
            "request": request.physical_identity(),
            "balance_arithmetic_semantics": "underflow-aware-v1",
        }
    )
    try:
        pool.cache.put(previous_key, {"ok": True, "origin": "synthetic-previous-cache"})
        current_key = pool.cache_key(request)
        assert current_key != previous_key
        assert pool.cache.get(current_key) is None
        assert pool.cache.get(previous_key) == {
            "ok": True,
            "origin": "synthetic-previous-cache",
        }
    finally:
        pool.close()
