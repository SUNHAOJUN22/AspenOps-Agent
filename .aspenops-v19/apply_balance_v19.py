from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    if path.suffix == ".py":
        compile(text, path.as_posix(), "exec")
    path.write_text(text, encoding="utf-8", newline="\n")


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0 and new in text:
        return
    if count != 1:
        raise RuntimeError(f"expected one exact pattern in {path}, found {count}: {old!r}")
    _write(path, text.replace(old, new, 1))


def repair_models() -> None:
    path = ROOT / "src/aspenops_nexus/models.py"
    text = path.read_text(encoding="utf-8")

    old_fields = '''class BalanceSpec:
    name: str
    terms: tuple[BalanceTerm, ...]
    expected: float = 0.0
    abs_tol: float = 1e-6
    rel_tol: float = 1e-6
    floor: float = 1e-12
'''
    new_fields = '''class BalanceSpec:
    name: str
    terms: tuple[BalanceTerm, ...]
    expected: float = 0.0
    abs_tol: float = 1e-6
    rel_tol: float = 1e-6
    floor: float = 1e-12
    dimension: str | None = None
    base_unit: str | None = None
'''
    if old_fields in text:
        text = text.replace(old_fields, new_fields, 1)
    elif new_fields not in text:
        raise RuntimeError("BalanceSpec field block was not found")

    old_parse = '''        abs_tol = _nonnegative_number(mapping.get("abs_tol", 1e-6), "balance abs_tol")
        rel_tol = _nonnegative_number(mapping.get("rel_tol", 1e-6), "balance rel_tol")
        floor = _nonnegative_number(mapping.get("floor", 1e-12), "balance floor")
        return cls(
            name=_text(mapping["name"], "balance name"),
            terms=terms,
            expected=_finite_number(mapping.get("expected", 0.0), "balance expected"),
            abs_tol=abs_tol,
            rel_tol=rel_tol,
            floor=floor,
        )
'''
    new_parse = '''        abs_tol = _nonnegative_number(mapping.get("abs_tol", 1e-6), "balance abs_tol")
        rel_tol = _nonnegative_number(mapping.get("rel_tol", 1e-6), "balance rel_tol")
        floor = _nonnegative_number(mapping.get("floor", 1e-12), "balance floor")
        dimension_name = _optional_text(mapping.get("dimension"), "balance dimension")
        base_unit = _optional_text(mapping.get("base_unit"), "balance base_unit")
        return cls(
            name=_text(mapping["name"], "balance name"),
            terms=terms,
            expected=_finite_number(mapping.get("expected", 0.0), "balance expected"),
            abs_tol=abs_tol,
            rel_tol=rel_tol,
            floor=floor,
            dimension=dimension_name,
            base_unit=base_unit,
        )
'''
    if old_parse in text:
        text = text.replace(old_parse, new_parse, 1)
    elif new_parse not in text:
        raise RuntimeError("BalanceSpec parser block was not found")

    old_serializers = '''def _balance_document(item: BalanceSpec) -> dict[str, Any]:
    return {
        "name": item.name,
        "terms": [_balance_term_dict(term) for term in item.terms],
        "expected": item.expected,
        "abs_tol": item.abs_tol,
        "rel_tol": item.rel_tol,
        "floor": item.floor,
    }


def _balance_identity(item: BalanceSpec) -> dict[str, Any]:
    return {
        "name": item.name,
        "terms": tuple(_balance_term_dict(term) for term in item.terms),
        "expected": item.expected,
        "abs_tol": item.abs_tol,
        "rel_tol": item.rel_tol,
        "floor": item.floor,
    }
'''
    new_serializers = '''def _balance_payload(item: BalanceSpec, *, identity: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": item.name,
        "terms": (
            tuple(_balance_term_dict(term) for term in item.terms)
            if identity
            else [_balance_term_dict(term) for term in item.terms]
        ),
        "expected": item.expected,
        "abs_tol": item.abs_tol,
        "rel_tol": item.rel_tol,
        "floor": item.floor,
    }
    if item.dimension is not None:
        payload["dimension"] = item.dimension
    if item.base_unit is not None:
        payload["base_unit"] = item.base_unit
    return payload


def _balance_document(item: BalanceSpec) -> dict[str, Any]:
    return _balance_payload(item, identity=False)


def _balance_identity(item: BalanceSpec) -> dict[str, Any]:
    return _balance_payload(item, identity=True)
'''
    if old_serializers in text:
        text = text.replace(old_serializers, new_serializers, 1)
    elif new_serializers not in text:
        raise RuntimeError("balance serializer blocks were not found")

    text = text.replace(
        "    balance_residuals: dict[str, dict[str, float]] = field(default_factory=dict)\n",
        "    balance_residuals: dict[str, dict[str, Any]] = field(default_factory=dict)\n",
        1,
    )

    old_result_parse = '''        balances: dict[str, dict[str, float]] = {}
        for name, raw_detail in raw_balances.items():
            detail = _object(raw_detail, f"result balance_residuals[{name}]")
            normalized_detail: dict[str, float] = {}
            for key, value in detail.items():
                normalized_detail[str(key)] = _finite_number(
                    value,
                    f"result balance_residuals[{name}].{key}",
                )
            balances[str(name)] = normalized_detail
'''
    new_result_parse = '''        balances: dict[str, dict[str, Any]] = {}
        for name, raw_detail in raw_balances.items():
            detail = _object(raw_detail, f"result balance_residuals[{name}]")
            normalized_detail: dict[str, Any] = {}
            for key, value in detail.items():
                label = f"result balance_residuals[{name}].{key}"
                if value is None or isinstance(value, str | bool):
                    normalized_detail[str(key)] = value
                elif isinstance(value, int | float):
                    normalized_detail[str(key)] = _finite_number(value, label)
                else:
                    raise ValueError(f"{label} must be a finite scalar JSON value or null")
            balances[str(name)] = normalized_detail
'''
    if old_result_parse in text:
        text = text.replace(old_result_parse, new_result_parse, 1)
    elif new_result_parse not in text:
        raise RuntimeError("balance result parser block was not found")

    _write(path, text)


def repair_evaluation_plan() -> None:
    path = ROOT / "src/aspenops_nexus/evaluation_plan.py"
    text = path.read_text(encoding="utf-8")
    if "from .units import dimension as unit_dimension\n" not in text:
        text = text.replace(
            "from .registry import NodeRegistry, RegistryError, ResolvedNode\n",
            "from .registry import NodeRegistry, RegistryError, ResolvedNode\n"
            "from .units import dimension as unit_dimension\n",
            1,
        )

    old_compiled = '''class CompiledBalance:
    spec: BalanceSpec
    terms: tuple[CompiledBalanceTerm, ...]
'''
    new_compiled = '''class CompiledBalance:
    spec: BalanceSpec
    terms: tuple[CompiledBalanceTerm, ...]
    dimension: str
    base_unit: str
'''
    if old_compiled in text:
        text = text.replace(old_compiled, new_compiled, 1)
    elif new_compiled not in text:
        raise RuntimeError("CompiledBalance block was not found")

    old_loop = '''        balances: list[CompiledBalance] = []
        for balance_spec in request.balances:
            terms: list[CompiledBalanceTerm] = []
            for term_spec in balance_spec.terms:
                term_node, identity = resolve_read_node(term_spec.key, term_spec.identifiers)
                terms.append(CompiledBalanceTerm(term_spec, term_node, identity))
            balances.append(CompiledBalance(balance_spec, tuple(terms)))
'''
    new_loop = '''        balances: list[CompiledBalance] = []
        for balance_spec in request.balances:
            terms: list[CompiledBalanceTerm] = []
            effective_units: list[str] = []
            inferred_dimensions: set[str] = set()
            for term_spec in balance_spec.terms:
                term_node, identity = resolve_read_node(term_spec.key, term_spec.identifiers)
                native_unit = term_node.native_unit
                if native_unit is None:
                    raise ValueError(
                        f"Balance {balance_spec.name} term {identity} has no registered native unit"
                    )
                native_dimension = unit_dimension(native_unit)
                effective_unit = term_spec.unit or native_unit
                effective_dimension = unit_dimension(effective_unit)
                if native_dimension != effective_dimension:
                    raise ValueError(
                        f"Balance {balance_spec.name} term {identity} requests incompatible unit "
                        f"{effective_unit!r} for registered unit {native_unit!r}"
                    )
                if effective_dimension is None:
                    raise ValueError(
                        f"Balance {balance_spec.name} term {identity} has no physical dimension"
                    )
                effective_units.append(effective_unit)
                inferred_dimensions.add(effective_dimension)
                terms.append(CompiledBalanceTerm(term_spec, term_node, identity))
            if len(inferred_dimensions) != 1:
                observed = ", ".join(sorted(inferred_dimensions))
                raise ValueError(
                    f"Balance {balance_spec.name} mixes physical dimensions: {observed}"
                )
            inferred_dimension = next(iter(inferred_dimensions))
            if (
                balance_spec.dimension is not None
                and balance_spec.dimension != inferred_dimension
            ):
                raise ValueError(
                    f"Balance {balance_spec.name} declares dimension "
                    f"{balance_spec.dimension!r} but terms are {inferred_dimension!r}"
                )
            resolved_dimension = balance_spec.dimension or inferred_dimension
            resolved_base_unit = balance_spec.base_unit or effective_units[0]
            base_dimension = unit_dimension(resolved_base_unit)
            if base_dimension != resolved_dimension:
                raise ValueError(
                    f"Balance {balance_spec.name} base unit {resolved_base_unit!r} has "
                    f"dimension {base_dimension!r}, expected {resolved_dimension!r}"
                )
            balances.append(
                CompiledBalance(
                    balance_spec,
                    tuple(terms),
                    resolved_dimension,
                    resolved_base_unit,
                )
            )
'''
    if old_loop in text:
        text = text.replace(old_loop, new_loop, 1)
    elif new_loop not in text:
        raise RuntimeError("balance compilation loop was not found")

    _write(path, text)


def repair_evaluation() -> None:
    path = ROOT / "src/aspenops_nexus/evaluation.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "    balance_residuals: dict[str, dict[str, float]] = {}\n",
        "    balance_residuals: dict[str, dict[str, Any]] = {}\n",
        1,
    )

    start_marker = "        non_finite_balances: dict[str, list[dict[str, str]]] = {}\n"
    end_marker = "        if non_finite_balances:\n            diagnostics[\"non_finite_balances\"] = non_finite_balances\n"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        if '"status": "invalid"' in text and "compiled_balance.base_unit" in text:
            _write(path, text)
            return
        raise RuntimeError("evaluation balance block was not found")
    end += len(end_marker)

    replacement = '''        invalid_balances: dict[str, list[dict[str, str]]] = {}
        for compiled_balance in active_plan.balances:
            name = compiled_balance.spec.name
            signed_terms: list[float] = []
            absolute_terms: list[float] = []
            invalid_terms: list[dict[str, str]] = []
            for compiled_term in compiled_balance.terms:
                converted = _converted(
                    raw_by_identity[compiled_term.identity],
                    compiled_term.node,
                    compiled_balance.base_unit,
                )
                try:
                    numeric = _numeric_value(converted)
                except TypeError:
                    invalid_terms.append(
                        {
                            "identity": compiled_term.identity,
                            "value": f"non_numeric:{type(converted).__name__}",
                        }
                    )
                    continue
                except ValueError:
                    invalid_terms.append(
                        {
                            "identity": compiled_term.identity,
                            "value": _non_finite_label(float(converted)),
                        }
                    )
                    continue
                signed = compiled_term.spec.coefficient * numeric
                if not math.isfinite(signed):
                    invalid_terms.append(
                        {
                            "identity": compiled_term.identity,
                            "value": "derived_overflow",
                        }
                    )
                    continue
                signed_terms.append(signed)
                absolute_terms.append(abs(signed))
            if invalid_terms:
                balance_residuals[name] = {
                    "status": "invalid",
                    "passed": False,
                    "dimension": compiled_balance.dimension,
                    "unit": compiled_balance.base_unit,
                    "residual": None,
                    "absolute": None,
                    "scale": None,
                    "relative": None,
                    "expected": compiled_balance.spec.expected,
                    "abs_tol": compiled_balance.spec.abs_tol,
                    "rel_tol": compiled_balance.spec.rel_tol,
                    "floor": compiled_balance.spec.floor,
                }
                invalid_balances[name] = invalid_terms
                violations.append(f"balance_invalid:{name}")
                violations.append(f"balance_failed:{name}")
                feasible = False
                continue
            signed_sum = _safe_fsum(signed_terms)
            absolute_sum = _safe_fsum(absolute_terms)
            residual = signed_sum - compiled_balance.spec.expected
            scale = max(absolute_sum, compiled_balance.spec.floor)
            relative = abs(residual) / scale if scale > 0 else math.inf
            if not all(math.isfinite(item) for item in (residual, scale, relative)):
                balance_residuals[name] = {
                    "status": "invalid",
                    "passed": False,
                    "dimension": compiled_balance.dimension,
                    "unit": compiled_balance.base_unit,
                    "residual": None,
                    "absolute": None,
                    "scale": None,
                    "relative": None,
                    "expected": compiled_balance.spec.expected,
                    "abs_tol": compiled_balance.spec.abs_tol,
                    "rel_tol": compiled_balance.spec.rel_tol,
                    "floor": compiled_balance.spec.floor,
                }
                invalid_balances[name] = [
                    {"identity": "derived_balance", "value": "derived_overflow"}
                ]
                violations.append(f"balance_invalid:{name}")
                violations.append(f"balance_failed:{name}")
                feasible = False
                continue
            passed = (
                abs(residual) <= compiled_balance.spec.abs_tol
                or relative <= compiled_balance.spec.rel_tol
            )
            balance_residuals[name] = {
                "status": "pass" if passed else "fail",
                "passed": passed,
                "dimension": compiled_balance.dimension,
                "unit": compiled_balance.base_unit,
                "residual": residual,
                "absolute": abs(residual),
                "scale": scale,
                "relative": relative,
                "expected": compiled_balance.spec.expected,
                "abs_tol": compiled_balance.spec.abs_tol,
                "rel_tol": compiled_balance.spec.rel_tol,
                "floor": compiled_balance.spec.floor,
            }
            if not passed:
                violations.append(f"balance_failed:{name}")
                feasible = False
        if invalid_balances:
            diagnostics["invalid_balances"] = invalid_balances
'''
    text = text[:start] + replacement + text[end:]
    _write(path, text)


def add_tests() -> None:
    path = ROOT / "tests/test_balance_dimension_contract_v19.py"
    text = '''from __future__ import annotations

import json
import math
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
'''
    _write(path, text)


def main() -> int:
    repair_models()
    repair_evaluation_plan()
    repair_evaluation()
    add_tests()
    print(
        {
            "status": "APPLIED",
            "contract": "dimension-safe canonical balance v19",
            "files": [
                "src/aspenops_nexus/models.py",
                "src/aspenops_nexus/evaluation_plan.py",
                "src/aspenops_nexus/evaluation.py",
                "tests/test_balance_dimension_contract_v19.py",
            ],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
