from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, cast

BackendName = Literal["mock", "aspen_plus", "hysys"]
ConstraintOperator = Literal["<", "<=", ">", ">=", "=="]
ResetMode = Literal["reinitialize", "warm_start"]
CacheSource = Literal[
    "computed",
    "persistent_cache",
    "same_batch_dedup",
    "inflight_singleflight",
]


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConstraintSpec:
        operator = str(data.get("operator", ">="))
        if operator not in {"<", "<=", ">", ">=", "=="}:
            raise ValueError(f"Unsupported constraint operator: {operator}")
        tolerance = float(data.get("tolerance", 0.0))
        if tolerance < 0:
            raise ValueError("Constraint tolerance cannot be negative")
        return cls(
            key=str(data["key"]),
            identifiers={str(k): str(v) for k, v in data.get("identifiers", {}).items()},
            operator=cast(ConstraintOperator, operator),
            value=float(data["value"]),
            unit=None if data.get("unit") is None else str(data["unit"]),
            name=str(data.get("name", "")),
            tolerance=tolerance,
        )


@dataclass(frozen=True, slots=True)
class BalanceTerm:
    key: str
    identifiers: dict[str, str]
    coefficient: float
    unit: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalanceTerm:
        return cls(
            key=str(data["key"]),
            identifiers={str(k): str(v) for k, v in data.get("identifiers", {}).items()},
            coefficient=float(data.get("coefficient", 1.0)),
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
    def from_dict(cls, data: dict[str, Any]) -> BalanceSpec:
        terms = tuple(BalanceTerm.from_dict(item) for item in data.get("terms", []))
        if not terms:
            raise ValueError("A balance requires at least one term")
        abs_tol = float(data.get("abs_tol", 1e-6))
        rel_tol = float(data.get("rel_tol", 1e-6))
        floor = float(data.get("floor", 1e-12))
        if min(abs_tol, rel_tol, floor) < 0:
            raise ValueError("Balance tolerances and floor cannot be negative")
        return cls(
            name=str(data["name"]),
            terms=terms,
            expected=float(data.get("expected", 0.0)),
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
    reset_mode: ResetMode = "reinitialize"
    timeout_s: float = 1200.0
    metadata: dict[str, Any] = field(default_factory=dict)

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
        timeout_s = float(data.get("timeout_s", 1200.0))
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        return cls(
            model_path=str(data["model_path"]),
            registry_path=str(data["registry_path"]),
            backend=cast(BackendName, backend),
            writes=tuple(VariableWrite.from_dict(x) for x in data.get("writes", [])),
            reads=tuple(VariableRead.from_dict(x) for x in data.get("reads", [])),
            constraints=tuple(ConstraintSpec.from_dict(x) for x in data.get("constraints", [])),
            balances=tuple(BalanceSpec.from_dict(x) for x in data.get("balances", [])),
            reset_mode=cast(ResetMode, reset_mode),
            timeout_s=timeout_s,
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def reinitialize(self) -> bool:
        return self.reset_mode == "reinitialize"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def physical_identity(self) -> dict[str, Any]:
        """Return solver and verification semantics without locations or execution policy."""
        return {
            "backend": self.backend,
            "reset_mode": self.reset_mode,
            "writes": [asdict(item) for item in self.writes],
            "reads": [asdict(item) for item in self.reads],
            "constraints": [asdict(item) for item in self.constraints],
            "balances": [asdict(item) for item in self.balances],
        }


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
    balance_residuals: dict[str, dict[str, float]] = field(default_factory=dict)
    cache_source: CacheSource = "computed"
    cache_hit: bool = False
    request_hash: str = ""
    worker_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationResult:
        normalized = dict(data)
        normalized.setdefault("engine_ok", bool(normalized.get("communication_ok", False)))
        normalized.setdefault("cache_source", "computed")
        normalized.setdefault("cache_hit", normalized["cache_source"] != "computed")
        return cls(**normalized)
