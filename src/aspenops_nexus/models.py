from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, cast

BackendName = Literal["mock", "aspen_plus", "hysys"]
ConstraintOperator = Literal["<", "<=", ">", ">=", "=="]
ResetMode = Literal["reinitialize", "warm_start"]


def _finite_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric, not Boolean")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


@dataclass(frozen=True, slots=True)
class VariableWrite:
    key: str
    identifiers: dict[str, str]
    value: float | int | str | bool
    unit: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariableWrite:
        return cls(
            key=str(data["key"]),
            identifiers={str(k): str(v) for k, v in data.get("identifiers", {}).items()},
            value=data["value"],
            unit=None if data.get("unit") is None else str(data["unit"]),
        )


@dataclass(frozen=True, slots=True)
class VariableRead:
    key: str
    identifiers: dict[str, str]
    unit: str | None = None
    required: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariableRead:
        return cls(
            key=str(data["key"]),
            identifiers={str(k): str(v) for k, v in data.get("identifiers", {}).items()},
            unit=None if data.get("unit") is None else str(data["unit"]),
            required=bool(data.get("required", True)),
        )


@dataclass(frozen=True, slots=True)
class ConstraintSpec:
    key: str
    identifiers: dict[str, str]
    operator: ConstraintOperator
    value: float
    unit: str | None = None
    name: str = ""
    tolerance: float = 0.0
    scale: float | None = None
    weight: float = 1.0

    def __post_init__(self) -> None:
        if self.operator not in {"<", "<=", ">", ">=", "=="}:
            raise ValueError(f"Unsupported constraint operator: {self.operator}")
        if not math.isfinite(self.value):
            raise ValueError("Constraint value must be finite")
        if not math.isfinite(self.tolerance) or self.tolerance < 0.0:
            raise ValueError("Constraint tolerance must be finite and nonnegative")
        if self.scale is not None and (not math.isfinite(self.scale) or self.scale <= 0.0):
            raise ValueError("Constraint scale must be finite and strictly positive")
        if not math.isfinite(self.weight) or self.weight < 0.0:
            raise ValueError("Constraint weight must be finite and nonnegative")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConstraintSpec:
        operator = str(data.get("operator", ">="))
        if operator not in {"<", "<=", ">", ">=", "=="}:
            raise ValueError(f"Unsupported constraint operator: {operator}")
        raw_scale = data.get("scale")
        return cls(
            key=str(data["key"]),
            identifiers={str(k): str(v) for k, v in data.get("identifiers", {}).items()},
            operator=cast(ConstraintOperator, operator),
            value=_finite_float(data["value"], "constraint value"),
            unit=None if data.get("unit") is None else str(data["unit"]),
            name=str(data.get("name", "")),
            tolerance=_finite_float(data.get("tolerance", 0.0), "constraint tolerance"),
            scale=(
                None
                if raw_scale is None
                else _finite_float(raw_scale, "constraint normalization scale")
            ),
            weight=_finite_float(data.get("weight", 1.0), "constraint weight"),
        )


@dataclass(frozen=True, slots=True)
class BalanceTerm:
    key: str
    identifiers: dict[str, str]
    coefficient: float
    unit: str | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.coefficient):
            raise ValueError("Balance coefficient must be finite")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalanceTerm:
        return cls(
            key=str(data["key"]),
            identifiers={str(k): str(v) for k, v in data.get("identifiers", {}).items()},
            coefficient=_finite_float(data.get("coefficient", 1.0), "balance coefficient"),
            unit=None if data.get("unit") is None else str(data["unit"]),
        )


@dataclass(frozen=True, slots=True)
class BalanceSpec:
    name: str
    terms: tuple[BalanceTerm, ...]
    expected: float = 0.0
    unit: str | None = None
    abs_tol: float = 1e-6
    rel_tol: float = 1e-6
    floor: float = 1e-12

    def __post_init__(self) -> None:
        if not self.terms:
            raise ValueError("A balance requires at least one term")
        for name, value in (
            ("expected", self.expected),
            ("abs_tol", self.abs_tol),
            ("rel_tol", self.rel_tol),
            ("floor", self.floor),
        ):
            if not math.isfinite(value):
                raise ValueError(f"Balance {name} must be finite")
        if self.abs_tol < 0.0 or self.rel_tol < 0.0:
            raise ValueError("Balance tolerances cannot be negative")
        if self.floor <= 0.0:
            raise ValueError("Balance floor must be strictly positive")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalanceSpec:
        terms = tuple(BalanceTerm.from_dict(item) for item in data.get("terms", []))
        return cls(
            name=str(data["name"]),
            terms=terms,
            expected=_finite_float(data.get("expected", 0.0), "balance expected value"),
            unit=None if data.get("unit") is None else str(data["unit"]),
            abs_tol=_finite_float(data.get("abs_tol", 1e-6), "balance absolute tolerance"),
            rel_tol=_finite_float(data.get("rel_tol", 1e-6), "balance relative tolerance"),
            floor=_finite_float(data.get("floor", 1e-12), "balance scale floor"),
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
    reset_mode: ResetMode = "reinitialize"
    timeout_s: float = 1200.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.backend not in {"mock", "aspen_plus", "hysys"}:
            raise ValueError(f"Unsupported backend: {self.backend}")
        if self.reset_mode not in {"reinitialize", "warm_start"}:
            raise ValueError(f"Unsupported reset_mode: {self.reset_mode}")
        if not self.model_path.strip() or not self.registry_path.strip():
            raise ValueError("model_path and registry_path must not be blank")
        if not math.isfinite(self.timeout_s) or self.timeout_s <= 0.0:
            raise ValueError("timeout_s must be finite and positive")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationRequest:
        backend = str(data.get("backend", "mock"))
        if backend not in {"mock", "aspen_plus", "hysys"}:
            raise ValueError(f"Unsupported backend: {backend}")
        reset_raw = data.get("reset_mode")
        if reset_raw is None:
            reset_raw = "reinitialize" if bool(data.get("reinitialize", True)) else "warm_start"
        reset_mode = str(reset_raw)
        if reset_mode not in {"reinitialize", "warm_start"}:
            raise ValueError(f"Unsupported reset_mode: {reset_mode}")
        return cls(
            model_path=str(data["model_path"]),
            registry_path=str(data["registry_path"]),
            backend=cast(BackendName, backend),
            writes=tuple(VariableWrite.from_dict(x) for x in data.get("writes", [])),
            reads=tuple(VariableRead.from_dict(x) for x in data.get("reads", [])),
            constraints=tuple(ConstraintSpec.from_dict(x) for x in data.get("constraints", [])),
            balances=tuple(BalanceSpec.from_dict(x) for x in data.get("balances", [])),
            reset_mode=cast(ResetMode, reset_mode),
            timeout_s=_finite_float(data.get("timeout_s", 1200.0), "timeout_s"),
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def reinitialize(self) -> bool:
        return self.reset_mode == "reinitialize"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def physical_identity(self) -> dict[str, Any]:
        """Return only solver-relevant fields; labels never change cache identity."""
        identity = self.to_dict()
        identity.pop("metadata", None)
        return identity


@dataclass(slots=True)
class EvaluationResult:
    ok: bool
    communication_ok: bool
    engine_ok: bool
    converged: bool
    feasible: bool
    values: dict[str, Any]
    units: dict[str, str | None]
    violations: list[str]
    diagnostics: dict[str, Any]
    elapsed_s: float
    balance_residuals: dict[str, dict[str, float | str]] = field(default_factory=dict)
    cache_hit: bool = False
    request_hash: str = ""
    worker_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationResult:
        normalized = dict(data)
        normalized.setdefault("engine_ok", bool(normalized.get("communication_ok", False)))
        return cls(**normalized)
