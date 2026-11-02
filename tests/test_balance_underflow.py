from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus import RUNTIME_SCHEMA, __version__
from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.hashing import canonical_hash
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.pool import CasePool
from aspenops_nexus.registry import NodeRegistry, ResolvedNode

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"
MIN_POSITIVE = math.nextafter(0.0, 1.0)


class ConstantFlowBackend(MockBackend):
    def __init__(self, value: float) -> None:
        super().__init__()
        self.value = value

    def read(self, node: ResolvedNode) -> Any:
        if node.key == "stream.input.mass_flow":
            return self.value
        return super().read(node)


def request_for_balance(
    *, coefficient: float = 1.0, floor: float = 1.0, abs_tol: float = 0.0, rel_tol: float = 0.0
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
                            "identifiers": {"stream": "FEED"},
                            "coefficient": coefficient,
                            "unit": "kg/h",
                        }
                    ],
                    "abs_tol": abs_tol,
                    "rel_tol": rel_tol,
                    "floor": floor,
                }
            ],
        }
    )


def evaluate_flow(value: float, request: EvaluationRequest) -> EvaluationResult:
    backend = ConstantFlowBackend(value)
    backend.open(MODEL)
    try:
        result = evaluate(backend, NodeRegistry(REGISTRY), request)
    finally:
        backend.close()
    # Numerical diagnostics must remain finite JSON and survive the IPC/cache format.
    return EvaluationResult.from_dict(json.loads(json.dumps(result.to_dict(), allow_nan=False)))


@pytest.mark.parametrize("coefficient", [0.125, -0.125])
def test_nonzero_weighted_balance_term_must_not_underflow_to_a_pass(coefficient: float) -> None:
    value = MIN_POSITIVE
    assert coefficient * value == 0.0
    result = evaluate_flow(value, request_for_balance(coefficient=coefficient))
    assert not result.ok
    assert not result.feasible
    assert result.balance_residuals["mass"]["status"] == "invalid"
    assert result.balance_residuals["mass"]["residual"] is None
    assert "balance_underflow:mass" in result.violations
    assert "balance_invalid:mass" in result.violations
    assert result.diagnostics["invalid_balances"]["mass"][0]["value"] == "derived_underflow"
    assert "mass" not in result.diagnostics.get("non_finite_balances", {})


@pytest.mark.parametrize("value,coefficient", [(0.0, MIN_POSITIVE), (MIN_POSITIVE, 0.0)])
def test_exact_zero_balance_product_remains_valid(value: float, coefficient: float) -> None:
    result = evaluate_flow(value, request_for_balance(coefficient=coefficient))
    assert result.ok
    assert result.balance_residuals["mass"]["residual"] == 0.0


@pytest.mark.parametrize("value", [1e-300, -1e-300])
@pytest.mark.parametrize(
    "abs_tol,rel_tol,expected",
    [(0.0, 0.0, False), (0.0, MIN_POSITIVE, True), (1e-300, 0.0, True)],
)
def test_underflowed_relative_balance_preserves_tolerance_decision(
    value: float, abs_tol: float, rel_tol: float, expected: bool
) -> None:
    assert abs(value) / 1e308 == 0.0
    result = evaluate_flow(
        value, request_for_balance(floor=1e308, abs_tol=abs_tol, rel_tol=rel_tol)
    )
    detail = result.balance_residuals["mass"]
    assert result.ok is expected
    assert detail["passed"] is expected
    assert detail["residual"] == value
    assert detail["relative"] == MIN_POSITIVE
    assert detail["relative_upper_bound"] is True


def test_representable_subnormal_balance_is_preserved() -> None:
    result = evaluate_flow(MIN_POSITIVE, request_for_balance())
    assert not result.ok
    detail = result.balance_residuals["mass"]
    assert detail["status"] == "fail"
    assert detail["residual"] == detail["relative"] == MIN_POSITIVE
    assert "relative_upper_bound" not in detail


def test_balance_arithmetic_change_cannot_replay_legacy_cached_pass(tmp_path: Path) -> None:
    request = request_for_balance()
    pool = CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )
    legacy_key = canonical_hash(
        {
            "schema": RUNTIME_SCHEMA,
            "runtime_version": __version__,
            "backend": pool.backend_name,
            "runtime_identity": pool._runtime_cache_identity(),
            "model_sha256": pool.model_sha256,
            "registry_sha256": pool._registry_digest(),
            "request": request.physical_identity(),
        }
    )
    try:
        pool.cache.put(legacy_key, {"ok": True, "origin": "synthetic-legacy-cache"})
        key = pool.cache_key(request)
        assert key != legacy_key
        assert pool._key_requests([request, request]) == [(key, request), (key, request)]
        assert pool.cache.get(key) is None
        assert pool.cache.get(legacy_key) == {"ok": True, "origin": "synthetic-legacy-cache"}
    finally:
        pool.close()
