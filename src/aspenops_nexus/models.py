from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, cast

from .units import dimension

BackendName = Literal["mock", "aspen_plus", "hysys"]
ConstraintOperator = Literal["<", "<=", ">", ">=", "=="]
ResetMode = Literal["reinitialize", "warm_start"]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def _strict_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be Boolean")
    return value


def _string(value: Any, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} must not be blank")
    return value


def _unit(value: Any, name: str) -> str | None:
    if value is None:
        return None
    unit = _string(value, name)
    dimension(unit)
    return unit


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    output: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"{name} keys must be strings")
        output[key] = item
    return output


def _identifiers(value: Any) -> dict[str, str]:
    raw = _mapping(value, "identifiers")
    identifiers: dict[str, str] = {}
    for key, item in raw.items():
        identifiers[key] = _string(item, f"identifier {key}")
    return identifiers


def _sequence(value: Any, name: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise TypeError(f"{name} must be an array")
    return list(value)


def _reject_unknown(data: Mapping[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(str(key) for key in data if key not in allowed)
    if unknown:
        raise ValueError(f"Unknown fields in {name}: {', '.join(unknown)}")


def _copy_json(value: Any, name: str) -> Any:
    if value is None or isinstance(value, bool | str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{name} object keys must be strings")
            output[key] = _copy_json(item, f"{name}.{key}")
        return output
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_copy_json(item, f"{name}[]") for item in value]
    raise TypeError(f"{name} contains unsupported JSON type {type(value).__name__}")


def _json_object(value: Any, name: str) -> dict[str, Any]:
    copied = _copy_json(value, name)
    if not isinstance(copied, dict):
        raise TypeError(f"{name} must be a JSON object")
    return copied


def _write_value(value: Any) -> float | int | str | bool:
    if isinstance(value, bool | str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("write value must be finite")
        return value
    raise TypeError("write value must be a Boolean, string, integer or finite float")


def _reference(key: str, identifiers: Mapping[str, str]) -> tuple[str, tuple[tuple[str, str], ...]]:
    return key, tuple(sorted(identifiers.items()))


@dataclass(frozen=True, slots=True)
class VariableWrite:
    key: str
    identifiers: dict[str, str]
    value: float | int | str | bool
    unit: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _string(self.key, "write key"))
        object.__setattr__(self, "identifiers", _identifiers(self.identifiers))
        object.__setattr__(self, "value", _write_value(self.value))
        object.__setattr__(self, "unit", _unit(self.unit, "write unit"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariableWrite:
        _reject_unknown(data, {"key", "identifiers", "value", "unit"}, "VariableWrite")
        if "key" not in data or "value" not in data:
            raise ValueError("VariableWrite requires key and value")
        return cls(
            key=data["key"],
            identifiers=_identifiers(data.get("identifiers", {})),
            value=data["value"],
            unit=data.get("unit"),
        )


@dataclass(frozen=True, slots=True)
class VariableRead:
    key: str
    identifiers: dict[str, str]
    unit: str | None = None
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _string(self.key, "read key"))
        object.__setattr__(self, "identifiers", _identifiers(self.identifiers))
        object.__setattr__(self, "unit", _unit(self.unit, "read unit"))
        object.__setattr__(self, "required", _strict_bool(self.required, "read required"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariableRead:
        _reject_unknown(data, {"key", "identifiers", "unit", "required"}, "VariableRead")
        if "key" not in data:
            raise ValueError("VariableRead requires key")
        return cls(
            key=data["key"],
            identifiers=_identifiers(data.get("identifiers", {})),
            unit=data.get("unit"),
            required=_strict_bool(data.get("required", True), "read required"),
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
        object.__setattr__(self, "key", _string(self.key, "constraint key"))
        object.__setattr__(self, "identifiers", _identifiers(self.identifiers))
        if self.operator not in {"<", "<=", ">", ">=", "=="}:
            raise ValueError(f"Unsupported constraint operator: {self.operator}")
        object.__setattr__(self, "value", _finite_float(self.value, "constraint value"))
        object.__setattr__(self, "unit", _unit(self.unit, "constraint unit"))
        object.__setattr__(self, "name", _string(self.name, "constraint name", allow_empty=True))
        tolerance = _finite_float(self.tolerance, "constraint tolerance")
        if tolerance < 0.0:
            raise ValueError("Constraint tolerance must be nonnegative")
        object.__setattr__(self, "tolerance", tolerance)
        if self.scale is not None:
            scale = _finite_float(self.scale, "constraint normalization scale")
            if scale <= 0.0:
                raise ValueError("Constraint scale must be strictly positive")
            object.__setattr__(self, "scale", scale)
        weight = _finite_float(self.weight, "constraint weight")
        if weight < 0.0:
            raise ValueError("Constraint weight must be nonnegative")
        object.__setattr__(self, "weight", weight)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConstraintSpec:
        _reject_unknown(
            data,
            {"key", "identifiers", "operator", "value", "unit", "name", "tolerance", "scale", "weight"},
            "ConstraintSpec",
        )
        if "key" not in data or "value" not in data:
            raise ValueError("ConstraintSpec requires key and value")
        operator = data.get("operator", ">=")
        if not isinstance(operator, str) or operator not in {"<", "<=", ">", ">=", "=="}:
            raise ValueError(f"Unsupported constraint operator: {operator}")
        return cls(
            key=data["key"],
            identifiers=_identifiers(data.get("identifiers", {})),
            operator=cast(ConstraintOperator, operator),
            value=data["value"],
            unit=data.get("unit"),
            name=data.get("name", ""),
            tolerance=data.get("tolerance", 0.0),
            scale=data.get("scale"),
            weight=data.get("weight", 1.0),
        )


@dataclass(frozen=True, slots=True)
class BalanceTerm:
    key: str
    identifiers: dict[str, str]
    coefficient: float
    unit: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _string(self.key, "balance term key"))
        object.__setattr__(self, "identifiers", _identifiers(self.identifiers))
        object.__setattr__(
            self,
            "coefficient",
            _finite_float(self.coefficient, "balance coefficient"),
        )
        object.__setattr__(self, "unit", _unit(self.unit, "balance term unit"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalanceTerm:
        _reject_unknown(data, {"key", "identifiers", "coefficient", "unit"}, "BalanceTerm")
        if "key" not in data:
            raise ValueError("BalanceTerm requires key")
        return cls(
            key=data["key"],
            identifiers=_identifiers(data.get("identifiers", {})),
            coefficient=data.get("coefficient", 1.0),
            unit=data.get("unit"),
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
        object.__setattr__(self, "name", _string(self.name, "balance name"))
        terms = tuple(self.terms)
        if not terms or not all(isinstance(term, BalanceTerm) for term in terms):
            raise ValueError("A balance requires at least one BalanceTerm")
        object.__setattr__(self, "terms", terms)
        object.__setattr__(self, "expected", _finite_float(self.expected, "balance expected"))
        object.__setattr__(self, "unit", _unit(self.unit, "balance unit"))
        abs_tol = _finite_float(self.abs_tol, "balance absolute tolerance")
        rel_tol = _finite_float(self.rel_tol, "balance relative tolerance")
        floor = _finite_float(self.floor, "balance scale floor")
        if abs_tol < 0.0 or rel_tol < 0.0:
            raise ValueError("Balance tolerances cannot be negative")
        if floor <= 0.0:
            raise ValueError("Balance floor must be strictly positive")
        object.__setattr__(self, "abs_tol", abs_tol)
        object.__setattr__(self, "rel_tol", rel_tol)
        object.__setattr__(self, "floor", floor)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalanceSpec:
        _reject_unknown(
            data,
            {"name", "terms", "expected", "unit", "abs_tol", "rel_tol", "floor"},
            "BalanceSpec",
        )
        if "name" not in data:
            raise ValueError("BalanceSpec requires name")
        terms = tuple(
            BalanceTerm.from_dict(_mapping(item, "balance term"))
            for item in _sequence(data.get("terms", []), "balance terms")
        )
        return cls(
            name=data["name"],
            terms=terms,
            expected=data.get("expected", 0.0),
            unit=data.get("unit"),
            abs_tol=data.get("abs_tol", 1e-6),
            rel_tol=data.get("rel_tol", 1e-6),
            floor=data.get("floor", 1e-12),
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
        object.__setattr__(self, "model_path", _string(self.model_path, "model_path"))
        object.__setattr__(self, "registry_path", _string(self.registry_path, "registry_path"))
        if self.backend not in {"mock", "aspen_plus", "hysys"}:
            raise ValueError(f"Unsupported backend: {self.backend}")
        if self.reset_mode not in {"reinitialize", "warm_start"}:
            raise ValueError(f"Unsupported reset_mode: {self.reset_mode}")
        writes = tuple(self.writes)
        reads = tuple(self.reads)
        constraints = tuple(self.constraints)
        balances = tuple(self.balances)
        if not all(isinstance(item, VariableWrite) for item in writes):
            raise TypeError("writes must contain only VariableWrite values")
        if not all(isinstance(item, VariableRead) for item in reads):
            raise TypeError("reads must contain only VariableRead values")
        if not all(isinstance(item, ConstraintSpec) for item in constraints):
            raise TypeError("constraints must contain only ConstraintSpec values")
        if not all(isinstance(item, BalanceSpec) for item in balances):
            raise TypeError("balances must contain only BalanceSpec values")
        object.__setattr__(self, "writes", writes)
        object.__setattr__(self, "reads", reads)
        object.__setattr__(self, "constraints", constraints)
        object.__setattr__(self, "balances", balances)
        write_references = [_reference(item.key, item.identifiers) for item in writes]
        read_references = [_reference(item.key, item.identifiers) for item in reads]
        if len(write_references) != len(set(write_references)):
            raise ValueError("Duplicate write destinations are not allowed")
        if len(read_references) != len(set(read_references)):
            raise ValueError("Duplicate read destinations are not allowed")
        constraint_names = [item.name for item in constraints if item.name]
        if len(constraint_names) != len(set(constraint_names)):
            raise ValueError("Explicit constraint names must be unique")
        balance_names = [item.name for item in balances]
        if len(balance_names) != len(set(balance_names)):
            raise ValueError("Balance names must be unique")
        timeout = _finite_float(self.timeout_s, "timeout_s")
        if timeout <= 0.0:
            raise ValueError("timeout_s must be positive")
        object.__setattr__(self, "timeout_s", timeout)
        object.__setattr__(self, "metadata", _json_object(self.metadata, "metadata"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationRequest:
        _reject_unknown(
            data,
            {
                "model_path",
                "registry_path",
                "backend",
                "writes",
                "reads",
                "constraints",
                "balances",
                "reset_mode",
                "reinitialize",
                "timeout_s",
                "metadata",
            },
            "EvaluationRequest",
        )
        if "model_path" not in data or "registry_path" not in data:
            raise ValueError("EvaluationRequest requires model_path and registry_path")
        backend = data.get("backend", "mock")
        if not isinstance(backend, str) or backend not in {"mock", "aspen_plus", "hysys"}:
            raise ValueError(f"Unsupported backend: {backend}")
        legacy_reinitialize: bool | None = None
        if "reinitialize" in data:
            legacy_reinitialize = _strict_bool(data["reinitialize"], "reinitialize")
        reset_raw = data.get("reset_mode")
        if reset_raw is None:
            reset_raw = (
                "reinitialize"
                if legacy_reinitialize is None or legacy_reinitialize
                else "warm_start"
            )
        if not isinstance(reset_raw, str) or reset_raw not in {"reinitialize", "warm_start"}:
            raise ValueError(f"Unsupported reset_mode: {reset_raw}")
        if legacy_reinitialize is not None:
            expected_reset = "reinitialize" if legacy_reinitialize else "warm_start"
            if reset_raw != expected_reset:
                raise ValueError("reset_mode conflicts with legacy reinitialize")
        writes = tuple(
            VariableWrite.from_dict(_mapping(item, "write"))
            for item in _sequence(data.get("writes", []), "writes")
        )
        reads = tuple(
            VariableRead.from_dict(_mapping(item, "read"))
            for item in _sequence(data.get("reads", []), "reads")
        )
        constraints = tuple(
            ConstraintSpec.from_dict(_mapping(item, "constraint"))
            for item in _sequence(data.get("constraints", []), "constraints")
        )
        balances = tuple(
            BalanceSpec.from_dict(_mapping(item, "balance"))
            for item in _sequence(data.get("balances", []), "balances")
        )
        return cls(
            model_path=data["model_path"],
            registry_path=data["registry_path"],
            backend=cast(BackendName, backend),
            writes=writes,
            reads=reads,
            constraints=constraints,
            balances=balances,
            reset_mode=cast(ResetMode, reset_raw),
            timeout_s=data.get("timeout_s", 1200.0),
            metadata=_json_object(data.get("metadata", {}), "metadata"),
        )

    @property
    def reinitialize(self) -> bool:
        return self.reset_mode == "reinitialize"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def physical_identity(self) -> dict[str, Any]:
        """Return solver and verification semantics, excluding location and execution policy."""
        identity = self.to_dict()
        for nonphysical_field in ("model_path", "registry_path", "timeout_s", "metadata"):
            identity.pop(nonphysical_field, None)
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
    balance_residuals: dict[str, dict[str, Any]] = field(default_factory=dict)
    cache_hit: bool = False
    request_hash: str = ""
    worker_id: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "ok",
            "communication_ok",
            "engine_ok",
            "converged",
            "feasible",
            "cache_hit",
        ):
            setattr(self, field_name, _strict_bool(getattr(self, field_name), field_name))
        expected_ok = self.communication_ok and self.engine_ok and self.converged and self.feasible
        if self.ok != expected_ok:
            raise ValueError("ok must equal communication_ok AND engine_ok AND converged AND feasible")
        self.values = _json_object(self.values, "values")
        raw_units = _mapping(self.units, "units")
        normalized_units: dict[str, str | None] = {}
        for key, value in raw_units.items():
            normalized_units[key] = _unit(value, f"unit for {key}")
        if set(normalized_units) != set(self.values):
            raise ValueError("values and units must contain exactly the same keys")
        self.units = normalized_units
        if not isinstance(self.violations, Sequence) or isinstance(
            self.violations, str | bytes | bytearray
        ):
            raise TypeError("violations must be an array")
        self.violations = [
            _string(item, "violation") for item in self.violations
        ]
        self.diagnostics = _json_object(self.diagnostics, "diagnostics")
        elapsed = _finite_float(self.elapsed_s, "elapsed_s")
        if elapsed < 0.0:
            raise ValueError("elapsed_s must be nonnegative")
        self.elapsed_s = elapsed
        raw_balances = _mapping(self.balance_residuals, "balance_residuals")
        balances: dict[str, dict[str, Any]] = {}
        for key, value in raw_balances.items():
            balances[key] = _json_object(value, f"balance_residuals.{key}")
        self.balance_residuals = balances
        self.request_hash = _string(self.request_hash, "request_hash", allow_empty=True)
        if self.request_hash and not _SHA256_RE.fullmatch(self.request_hash):
            raise ValueError("request_hash must be empty or a lowercase SHA-256 digest")
        if self.worker_id is not None:
            if (
                isinstance(self.worker_id, bool)
                or not isinstance(self.worker_id, int)
                or self.worker_id < 0
            ):
                raise ValueError("worker_id must be a nonnegative integer or None")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationResult:
        _reject_unknown(
            data,
            {
                "ok",
                "communication_ok",
                "engine_ok",
                "converged",
                "feasible",
                "values",
                "units",
                "violations",
                "diagnostics",
                "elapsed_s",
                "balance_residuals",
                "cache_hit",
                "request_hash",
                "worker_id",
            },
            "EvaluationResult",
        )
        required = {
            "ok",
            "communication_ok",
            "converged",
            "feasible",
            "values",
            "units",
            "violations",
            "diagnostics",
            "elapsed_s",
        }
        missing = sorted(required - data.keys())
        if missing:
            raise ValueError(f"EvaluationResult missing fields: {', '.join(missing)}")
        communication_ok = _strict_bool(data["communication_ok"], "communication_ok")
        engine_ok = _strict_bool(data.get("engine_ok", communication_ok), "engine_ok")
        return cls(
            ok=_strict_bool(data["ok"], "ok"),
            communication_ok=communication_ok,
            engine_ok=engine_ok,
            converged=_strict_bool(data["converged"], "converged"),
            feasible=_strict_bool(data["feasible"], "feasible"),
            values=_json_object(data["values"], "values"),
            units=cast(dict[str, str | None], _mapping(data["units"], "units")),
            violations=[
                _string(item, "violation")
                for item in _sequence(data["violations"], "violations")
            ],
            diagnostics=_json_object(data["diagnostics"], "diagnostics"),
            elapsed_s=data["elapsed_s"],
            balance_residuals=cast(
                dict[str, dict[str, Any]],
                _mapping(data.get("balance_residuals", {}), "balance_residuals"),
            ),
            cache_hit=_strict_bool(data.get("cache_hit", False), "cache_hit"),
            request_hash=data.get("request_hash", ""),
            worker_id=data.get("worker_id"),
        )
