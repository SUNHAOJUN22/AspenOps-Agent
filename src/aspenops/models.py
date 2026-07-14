from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, cast

BackendName = Literal["mock", "aspen_plus", "hysys"]
ComparisonOperator = Literal["<", "<=", ">", ">=", "==", "!="]
ResetMode = Literal["reinitialize", "warm_start"]
Scalar = float | int | str | bool


def _identifiers(data: Any) -> dict[str, str]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("identifiers must be an object")
    return {str(key): str(value) for key, value in data.items()}


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric, not a Boolean")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _boolean(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    raise ValueError(f"{name} must be a Boolean")


def _operator(value: Any) -> ComparisonOperator:
    operator = str(value)
    if operator not in {"<", "<=", ">", ">=", "==", "!="}:
        raise ValueError(f"Unsupported comparison operator: {operator}")
    return cast(ComparisonOperator, operator)


@dataclass(frozen=True, slots=True)
class VariableWrite:
    key: str
    identifiers: dict[str, str]
    value: Scalar
    unit: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VariableWrite":
        value = data["value"]
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("write value must be finite")
        if not isinstance(value, (float, int, str, bool)):
            raise ValueError("write value must be a scalar")
        return cls(
            key=str(data["key"]),
            identifiers=_identifiers(data.get("identifiers")),
            value=value,
            unit=None if data.get("unit") is None else str(data["unit"]),
        )


@dataclass(frozen=True, slots=True)
class VariableRead:
    key: str
    identifiers: dict[str, str]
    unit: str | None = None
    required: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VariableRead":
        return cls(
            key=str(data["key"]),
            identifiers=_identifiers(data.get("identifiers")),
            unit=None if data.get("unit") is None else str(data["unit"]),
            required=_boolean(data.get("required", True), "required"),
        )


@dataclass(frozen=True, slots=True)
class ComparisonSpec:
    key: str
    identifiers: dict[str, str]
    operator: ComparisonOperator
    value: Scalar
    unit: str | None = None
    name: str = ""
    tolerance: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComparisonSpec":
        tolerance = _finite(data.get("tolerance", 0.0), "comparison tolerance")
        if tolerance < 0:
            raise ValueError("comparison tolerance cannot be negative")
        value = data["value"]
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("comparison value must be finite")
        if not isinstance(value, (float, int, str, bool)):
            raise ValueError("comparison value must be a scalar")
        return cls(
            key=str(data["key"]),
            identifiers=_identifiers(data.get("identifiers")),
            operator=_operator(data.get("operator", ">=")),
            value=value,
            unit=None if data.get("unit") is None else str(data["unit"]),
            name=str(data.get("name", "")),
            tolerance=tolerance,
        )


ConstraintSpec = ComparisonSpec
ConvergenceSpec = ComparisonSpec


@dataclass(frozen=True, slots=True)
class BalanceTerm:
    key: str
    identifiers: dict[str, str]
    coefficient: float
    unit: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BalanceTerm":
        return cls(
            key=str(data["key"]),
            identifiers=_identifiers(data.get("identifiers")),
            coefficient=_finite(data.get("coefficient", 1.0), "balance coefficient"),
            unit=None if data.get("unit") is None else str(data["unit"]),
        )


@dataclass(frozen=True, slots=True)
class BalanceSpec:
    name: str
    terms: tuple[BalanceTerm, ...]
    expected: float = 0.0
    abs_tol: float = 1e-6
    rel_tol: float = 1e-6
    floor: float = 1e-12

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BalanceSpec":
        terms = tuple(BalanceTerm.from_dict(item) for item in data.get("terms", []))
        if not terms:
            raise ValueError("A balance requires at least one term")
        abs_tol = _finite(data.get("abs_tol", 1e-6), "balance abs_tol")
        rel_tol = _finite(data.get("rel_tol", 1e-6), "balance rel_tol")
        floor = _finite(data.get("floor", 1e-12), "balance floor")
        if min(abs_tol, rel_tol) < 0:
            raise ValueError("Balance tolerances cannot be negative")
        if floor <= 0:
            raise ValueError("Balance floor must be positive")
        return cls(
            name=str(data["name"]),
            terms=terms,
            expected=_finite(data.get("expected", 0.0), "balance expected"),
            abs_tol=abs_tol,
            rel_tol=rel_tol,
            floor=floor,
        )


@dataclass(frozen=True, slots=True)
class EvaluationRequest:
    model_path: str
    registry_path: str
    backend: BackendName
    writes: tuple[VariableWrite, ...]
    reads: tuple[VariableRead, ...]
    constraints: tuple[ConstraintSpec, ...] = ()
    balances: tuple[BalanceSpec, ...] = ()
    convergence: ConvergenceSpec | None = None
    reset_mode: ResetMode = "reinitialize"
    timeout_s: float = 1200.0
    solver_options: dict[str, Scalar] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationRequest":
        backend = str(data.get("backend", "mock"))
        if backend not in {"mock", "aspen_plus", "hysys"}:
            raise ValueError(f"Unsupported backend: {backend}")
        reset_raw = data.get("reset_mode")
        if reset_raw is None:
            reset_raw = "reinitialize" if _boolean(data.get("reinitialize", True), "reinitialize") else "warm_start"
        reset_mode = str(reset_raw)
        if reset_mode not in {"reinitialize", "warm_start"}:
            raise ValueError(f"Unsupported reset_mode: {reset_mode}")
        timeout_s = _finite(data.get("timeout_s", 1200.0), "timeout_s")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        raw_solver = data.get("solver_options", {})
        if not isinstance(raw_solver, dict):
            raise ValueError("solver_options must be an object")
        solver_options: dict[str, Scalar] = {}
        for key, value in raw_solver.items():
            if not isinstance(value, (float, int, str, bool)):
                raise ValueError(f"solver_options[{key!r}] must be a scalar")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"solver_options[{key!r}] must be finite")
            solver_options[str(key)] = value
        convergence_data = data.get("convergence")
        raw_metadata = data.get("metadata", {})
        if not isinstance(raw_metadata, dict):
            raise ValueError("metadata must be an object")
        return cls(
            model_path=str(data["model_path"]), registry_path=str(data["registry_path"]),
            backend=cast(BackendName, backend),
            writes=tuple(VariableWrite.from_dict(item) for item in data.get("writes", [])),
            reads=tuple(VariableRead.from_dict(item) for item in data.get("reads", [])),
            constraints=tuple(ComparisonSpec.from_dict(item) for item in data.get("constraints", [])),
            balances=tuple(BalanceSpec.from_dict(item) for item in data.get("balances", [])),
            convergence=None if convergence_data is None else ComparisonSpec.from_dict(cast(dict[str, Any], convergence_data)),
            reset_mode=cast(ResetMode, reset_mode), timeout_s=timeout_s,
            solver_options=solver_options, metadata=dict(raw_metadata),
        )

    @property
    def reinitialize(self) -> bool:
        return self.reset_mode == "reinitialize"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def physical_identity(self) -> dict[str, Any]:
        return {
            "writes": [asdict(item) for item in self.writes],
            "reads": [asdict(item) for item in self.reads],
            "constraints": [asdict(item) for item in self.constraints],
            "balances": [asdict(item) for item in self.balances],
            "convergence": None if self.convergence is None else asdict(self.convergence),
            "reset_mode": self.reset_mode,
            "solver_options": dict(sorted(self.solver_options.items())),
        }


@dataclass(slots=True)
class EvaluationResult:
    ok: bool
    transport_ok: bool
    engine_ok: bool
    convergence_known: bool
    converged: bool
    constraints_ok: bool
    balances_ok: bool
    feasible: bool
    trusted_outputs: bool
    values: dict[str, Any]
    units: dict[str, str | None]
    violations: list[str]
    diagnostics: dict[str, Any]
    elapsed_s: float
    balance_residuals: dict[str, dict[str, Any]] = field(default_factory=dict)
    cache_hit: bool = False
    deduplicated: bool = False
    request_hash: str = ""
    worker_id: int | None = None

    @property
    def communication_ok(self) -> bool:
        return self.transport_ok

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["communication_ok"] = self.transport_ok
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationResult":
        normalized = dict(data)
        compatibility_transport = normalized.pop("communication_ok", normalized.get("engine_ok", False))
        normalized.setdefault("transport_ok", _boolean(compatibility_transport, "transport_ok"))
        normalized.pop("communication_ok", None)
        normalized.setdefault("convergence_known", _boolean(normalized.get("converged", False), "convergence_known"))
        normalized.setdefault("constraints_ok", _boolean(normalized.get("feasible", False), "constraints_ok"))
        normalized.setdefault("balances_ok", _boolean(normalized.get("feasible", False), "balances_ok"))
        normalized.setdefault("trusted_outputs", _boolean(normalized.get("converged", False), "trusted_outputs"))
        normalized.setdefault("deduplicated", False)
        for field_name in ("ok", "transport_ok", "engine_ok", "convergence_known", "converged", "constraints_ok", "balances_ok", "feasible", "trusted_outputs", "cache_hit", "deduplicated"):
            if field_name in normalized:
                normalized[field_name] = _boolean(normalized[field_name], field_name)
        return cls(**normalized)
