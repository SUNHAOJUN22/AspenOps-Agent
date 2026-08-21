from __future__ import annotations

import json
import math
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.evaluation_plan import EvaluationPlanCompiler
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.registry import NodeRegistry


class StaticBackend(MockBackend):
    def __init__(self, values: dict[str, Any]) -> None:
        super().__init__()
        self._values = dict(values)

    def open(self, model_path: Path, *, visible: bool = False) -> None:
        del visible
        self.model_path = model_path
        self.data = {}
        self._initial = dict(self._values)
        self.state = dict(self._values)

    def reinitialize(self) -> None:
        self.state = dict(self._values)

    def run(self) -> dict[str, Any]:
        self.solve_count += 1
        return {
            "engine_returned": True,
            "converged": True,
            "convergence_state": "converged",
        }

    def runtime_identity(self) -> dict[str, Any]:
        return {"backend": "mock", "engine": "static-balance-v19"}


def _registry(tmp_path: Path) -> NodeRegistry:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "name": "balance-v19",
                "version": "1",
                "nodes": {
                    "mass.hour": {
                        "access": "read",
                        "backend": "any",
                        "unit": "kg/h",
                        "paths": ["mass-hour"],
                        "locator": {"mock_key": "mass_hour"},
                    },
                    "mass.second": {
                        "access": "read",
                        "backend": "any",
                        "unit": "kg/s",
                        "paths": ["mass-second"],
                        "locator": {"mock_key": "mass_second"},
                    },
                    "power": {
                        "access": "read",
                        "backend": "any",
                        "unit": "kW",
                        "paths": ["power"],
                        "locator": {"mock_key": "power"},
                    },
                },
            },
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    return NodeRegistry(path)


def _request(tmp_path: Path, *, base_unit: str = "kg/s") -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(tmp_path / "static.json"),
            "registry_path": str(tmp_path / "registry.json"),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "mass",
                    "dimension": "mass_flow",
                    "base_unit": base_unit,
                    "terms": [
                        {"key": "mass.hour", "identifiers": {}, "coefficient": 1},
                        {"key": "mass.second", "identifiers": {}, "coefficient": -1},
                    ],
                    "expected": 0,
                    "abs_tol": 1e-12,
                    "rel_tol": 1e-12,
                    "floor": 1e-12,
                }
            ],
        }
    )


def test_mixed_dimension_balance_is_rejected_before_execution(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(tmp_path / "static.json"),
            "registry_path": str(tmp_path / "registry.json"),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "invalid",
                    "terms": [
                        {"key": "mass.hour", "identifiers": {}, "coefficient": 1},
                        {"key": "power", "identifiers": {}, "coefficient": -1},
                    ],
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="mixes physical dimensions"):
        EvaluationPlanCompiler.compile(registry, request)


def test_mass_balance_is_invariant_to_kg_per_hour_and_second(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    model = tmp_path / "static.json"
    model.write_text("{}", encoding="utf-8")
    outcomes = []
    for base_unit in ("kg/s", "kg/h"):
        backend = StaticBackend({"mass_hour": 3600.0, "mass_second": 1.0})
        backend.open(model)
        result = evaluate(backend, registry, _request(tmp_path, base_unit=base_unit))
        backend.close()
        outcomes.append(result)
        detail = result.balance_residuals["mass"]
        assert result.ok
        assert detail["status"] == "pass"
        assert detail["passed"] is True
        assert detail["residual"] == pytest.approx(0.0, abs=1e-15)
        assert detail["dimension"] == "mass_flow"
        assert detail["unit"] == base_unit
    assert outcomes[0].ok is outcomes[1].ok


def test_nonfinite_balance_is_invalid_not_zero(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    model = tmp_path / "static.json"
    model.write_text("{}", encoding="utf-8")
    backend = StaticBackend({"mass_hour": math.nan, "mass_second": 1.0})
    backend.open(model)
    result = evaluate(backend, registry, _request(tmp_path))
    backend.close()
    detail = result.balance_residuals["mass"]
    assert not result.ok
    assert detail["status"] == "invalid"
    assert detail["passed"] is False
    assert detail["residual"] is None
    assert detail["relative"] is None
    assert "balance_invalid:mass" in result.violations
    payload = result.to_dict()
    restored = EvaluationResult.from_dict(payload)
    assert restored.balance_residuals["mass"]["residual"] is None
    json.dumps(payload, allow_nan=False)


def test_legacy_balance_safely_infers_one_dimension_and_base_unit(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(tmp_path / "static.json"),
            "registry_path": str(tmp_path / "registry.json"),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "legacy",
                    "terms": [
                        {"key": "mass.hour", "identifiers": {}, "coefficient": 1},
                        {
                            "key": "mass.second",
                            "identifiers": {},
                            "coefficient": -1,
                            "unit": "kg/h",
                        },
                    ],
                }
            ],
        }
    )
    compiled = EvaluationPlanCompiler.compile(registry, request).balances[0]
    assert compiled.dimension == "mass_flow"
    assert compiled.base_unit == "kg/h"


def test_declared_balance_contracts_fail_closed_v19(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    common = {
        "model_path": str(tmp_path / "static.json"),
        "registry_path": str(tmp_path / "registry.json"),
        "backend": "mock",
        "writes": [],
        "reads": [],
    }
    wrong_dimension = EvaluationRequest.from_dict(
        {
            **common,
            "balances": [
                {
                    "name": "wrong-dimension",
                    "dimension": "power",
                    "terms": [
                        {"key": "mass.hour", "identifiers": {}, "coefficient": 1},
                        {"key": "mass.second", "identifiers": {}, "coefficient": -1},
                    ],
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="declares dimension"):
        EvaluationPlanCompiler.compile(registry, wrong_dimension)

    wrong_base = EvaluationRequest.from_dict(
        {
            **common,
            "balances": [
                {
                    "name": "wrong-base",
                    "dimension": "mass_flow",
                    "base_unit": "kW",
                    "terms": [
                        {"key": "mass.hour", "identifiers": {}, "coefficient": 1},
                        {"key": "mass.second", "identifiers": {}, "coefficient": -1},
                    ],
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="base unit"):
        EvaluationPlanCompiler.compile(registry, wrong_base)

    wrong_term_unit = EvaluationRequest.from_dict(
        {
            **common,
            "balances": [
                {
                    "name": "wrong-term-unit",
                    "terms": [
                        {
                            "key": "mass.hour",
                            "identifiers": {},
                            "coefficient": 1,
                            "unit": "kW",
                        }
                    ],
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="requests incompatible unit"):
        EvaluationPlanCompiler.compile(registry, wrong_term_unit)


def test_optional_balance_contract_fields_remain_explicit_in_documents_v19(
    tmp_path: Path,
) -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(tmp_path / "static.json"),
            "registry_path": str(tmp_path / "registry.json"),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "legacy",
                    "terms": [{"key": "mass.hour", "identifiers": {}, "coefficient": 1}],
                }
            ],
        }
    )
    balance = request.to_dict()["balances"][0]
    assert balance["dimension"] is None
    assert balance["base_unit"] is None
    assert request.physical_identity()["balances"][0]["dimension"] is None


def _compiled_mass_plan(tmp_path: Path, *, base_unit: str = "kg/h"):
    registry = _registry(tmp_path)
    return registry, EvaluationPlanCompiler.compile(
        registry,
        _request(tmp_path, base_unit=base_unit),
    )


def test_precompiled_balance_contract_failures_are_structured_v19(
    tmp_path: Path,
) -> None:
    registry, plan = _compiled_mass_plan(tmp_path)
    model = tmp_path / "static.json"
    model.write_text("{}", encoding="utf-8")

    empty_balance = replace(plan.balances[0], terms=())
    backend = StaticBackend({"mass_hour": 1.0, "mass_second": 1.0})
    backend.open(model)
    empty_result = evaluate(
        backend, registry, _request(tmp_path), plan=replace(plan, balances=(empty_balance,))
    )
    backend.close()
    assert not empty_result.ok
    assert "execution_error:ValueError" in empty_result.violations
    assert "no terms" in empty_result.diagnostics["exception"]

    first = plan.balances[0].terms[0]
    no_unit_first = replace(first, node=replace(first.node, native_unit=None))
    no_unit_balance = replace(plan.balances[0], base_unit=None, terms=(no_unit_first,))
    backend = StaticBackend({"mass_hour": 1.0, "mass_second": 1.0})
    backend.open(model)
    no_unit_result = evaluate(
        backend,
        registry,
        _request(tmp_path),
        plan=replace(plan, balances=(no_unit_balance,)),
    )
    backend.close()
    assert not no_unit_result.ok
    assert "execution_error:ValueError" in no_unit_result.violations
    assert "canonical base unit" in no_unit_result.diagnostics["exception"]


def test_balance_non_numeric_and_signed_overflow_are_invalid_v19(tmp_path: Path) -> None:
    registry, plan = _compiled_mass_plan(tmp_path)
    model = tmp_path / "static.json"
    model.write_text("{}", encoding="utf-8")

    backend = StaticBackend({"mass_hour": "not-a-number", "mass_second": 0.0})
    backend.open(model)
    non_numeric = evaluate(backend, registry, _request(tmp_path, base_unit="kg/h"), plan=plan)
    backend.close()
    assert not non_numeric.ok
    assert non_numeric.balance_residuals["mass"]["status"] == "invalid"
    assert non_numeric.diagnostics["invalid_balances"]["mass"][0]["value"] == "non_numeric:str"

    first = plan.balances[0].terms[0]
    overflowing_first = replace(first, spec=replace(first.spec, coefficient=2.0))
    overflow_balance = replace(
        plan.balances[0],
        terms=(overflowing_first, plan.balances[0].terms[1]),
    )
    backend = StaticBackend({"mass_hour": sys.float_info.max, "mass_second": 0.0})
    backend.open(model)
    overflow = evaluate(
        backend,
        registry,
        _request(tmp_path, base_unit="kg/h"),
        plan=replace(plan, balances=(overflow_balance,)),
    )
    backend.close()
    assert not overflow.ok
    assert overflow.diagnostics["invalid_balances"]["mass"][0]["value"] == "derived_overflow"
    assert "balance_non_finite:mass" in overflow.violations


def test_balance_aggregate_overflow_is_invalid_not_zero_v19(tmp_path: Path) -> None:
    registry, plan = _compiled_mass_plan(tmp_path)
    model = tmp_path / "static.json"
    model.write_text("{}", encoding="utf-8")
    second = plan.balances[0].terms[1]
    positive_second = replace(second, spec=replace(second.spec, coefficient=1.0))
    aggregate_balance = replace(
        plan.balances[0],
        terms=(plan.balances[0].terms[0], positive_second),
    )
    backend = StaticBackend(
        {"mass_hour": sys.float_info.max, "mass_second": sys.float_info.max / 3600.0}
    )
    backend.open(model)
    result = evaluate(
        backend,
        registry,
        _request(tmp_path, base_unit="kg/h"),
        plan=replace(plan, balances=(aggregate_balance,)),
    )
    backend.close()
    detail = result.balance_residuals["mass"]
    assert not result.ok
    assert detail["status"] == "invalid"
    assert detail["residual"] is None
    assert result.diagnostics["invalid_balances"]["mass"] == [
        {"identity": "derived_balance", "value": "derived_overflow"}
    ]
