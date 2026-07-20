from __future__ import annotations

import math
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


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _text(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    normalized = value.strip()
    if nonempty and not normalized:
        raise ValueError(f"{label} must be a non-empty string")
    return normalized


def _optional_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def _nonnegative_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a finite non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return number


def _positive_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a finite positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a finite positive number")
    return number


def _identifiers(value: Any, label: str) -> dict[str, str]:
    mapping = _object(value, label)
    identifiers: dict[str, str] = {}
    for raw_key, raw_value in mapping.items():
        key = _text(raw_key, f"{label} key")
        if isinstance(raw_value, bool):
            identifiers[key] = "true" if raw_value else "false"
        elif isinstance(raw_value, int | float):
            if isinstance(raw_value, float) and not math.isfinite(raw_value):
                raise ValueError(f"{label} values must be finite scalar JSON values")
            identifiers[key] = str(raw_value)
        elif isinstance(raw_value, str):
            identifiers[key] = raw_value
        else:
            raise ValueError(f"{label} values must be finite scalar JSON values")
    return identifiers


def _scalar(value: Any, label: str) -> float | int | str | bool:
    if isinstance(value, bool | str | int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError(f"{label} must be a finite scalar JSON value")


@dataclass(frozen=True, slots=True)
class VariableWrite:
    key: str
    identifiers: dict[str, str]
    value: float | int | str | bool
    unit: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariableWrite:
        mapping = _object(data, "write")
        if "key" not in mapping:
            raise ValueError("write is missing key")
        if "value" not in mapping:
            raise ValueError("write is missing value")
        return cls(
            key=_text(mapping["key"], "write key"),
            identifiers=_identifiers(mapping.get("identifiers", {}), "write identifiers"),
            value=_scalar(mapping["value"], "write value"),
            unit=_optional_text(mapping.get("unit"), "write unit"),
        )


@dataclass(frozen=True, slots=True)
class VariableRead:
    key: str
    identifiers: dict[str, str]
    unit: str | None = None
    required: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariableRead:
        mapping = _object(data, "read")
        if "key" not in mapping:
            raise ValueError("read is missing key")
        required = mapping.get("required", True)
        if not isinstance(required, bool):
            raise ValueError("read required must be a boolean")
        return cls(
            key=_text(mapping["key"], "read key"),
            identifiers=_identifiers(mapping.get("identifiers", {}), "read identifiers"),
            unit=_optional_text(mapping.get("unit"), "read unit"),
            required=required,
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
        mapping = _object(data, "constraint")
        if "key" not in mapping:
            raise ValueError("constraint is missing key")
        if "value" not in mapping:
            raise ValueError("constraint is missing value")
        operator_raw = mapping.get("operator", ">=")
        if not isinstance(operator_raw, str) or operator_raw not in {"<", "<=", ">", ">=", "=="}:
            raise ValueError(f"Unsupported constraint operator: {operator_raw}")
        tolerance = _finite_number(mapping.get("tolerance", 0.0), "constraint tolerance")
        if tolerance < 0:
            raise ValueError("Constraint tolerance cannot be negative")
        name_raw = mapping.get("name", "")
        if not isinstance(name_raw, str):
            raise ValueError("constraint name must be a string")
        return cls(
            key=_text(mapping["key"], "constraint key"),
            identifiers=_identifiers(
                mapping.get("identifiers", {}),
                "constraint identifiers",
            ),
            operator=cast(ConstraintOperator, operator_raw),
            value=_finite_number(mapping["value"], "constraint value"),
            unit=_optional_text(mapping.get("unit"), "constraint unit"),
            name=name_raw,
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
        mapping = _object(data, "balance term")
        if "key" not in mapping:
            raise ValueError("balance term is missing key")
        return cls(
            key=_text(mapping["key"], "balance term key"),
            identifiers=_identifiers(
                mapping.get("identifiers", {}),
                "balance term identifiers",
            ),
            coefficient=_finite_number(
                mapping.get("coefficient", 1.0),
                "balance coefficient",
            ),
            unit=_optional_text(mapping.get("unit"), "balance term unit"),
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
        mapping = _object(data, "balance")
        if "name" not in mapping:
            raise ValueError("balance is missing name")
        terms = tuple(
            BalanceTerm.from_dict(_object(item, f"balance terms[{index}]"))
            for index, item in enumerate(_array(mapping.get("terms", []), "balance terms"))
        )
        if not terms:
            raise ValueError("A balance requires at least one term")
        abs_tol = _nonnegative_number(mapping.get("abs_tol", 1e-6), "balance abs_tol")
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
        mapping = _object(data, "evaluation request")
        if "model_path" not in mapping:
            raise ValueError("evaluation request is missing model_path")
        if "registry_path" not in mapping:
            raise ValueError("evaluation request is missing registry_path")
        backend_raw = mapping.get("backend", "mock")
        if not isinstance(backend_raw, str) or backend_raw not in {"mock", "aspen_plus", "hysys"}:
            raise ValueError(f"Unsupported backend: {backend_raw}")
        reset_raw = mapping.get("reset_mode")
        if reset_raw is None:
            reinitialize = mapping.get("reinitialize", True)
            if not isinstance(reinitialize, bool):
                raise ValueError("reinitialize must be a boolean")
            reset_raw = "reinitialize" if reinitialize else "warm_start"
        if not isinstance(reset_raw, str) or reset_raw not in {"reinitialize", "warm_start"}:
            raise ValueError(f"Unsupported reset_mode: {reset_raw}")
        timeout_s = _positive_number(mapping.get("timeout_s", 1200.0), "timeout_s")
        metadata = _object(mapping.get("metadata", {}), "metadata")
        return cls(
            model_path=_text(mapping["model_path"], "model_path"),
            registry_path=_text(mapping["registry_path"], "registry_path"),
            backend=cast(BackendName, backend_raw),
            writes=tuple(
                VariableWrite.from_dict(_object(item, f"writes[{index}]"))
                for index, item in enumerate(_array(mapping.get("writes", []), "writes"))
            ),
            reads=tuple(
                VariableRead.from_dict(_object(item, f"reads[{index}]"))
                for index, item in enumerate(_array(mapping.get("reads", []), "reads"))
            ),
            constraints=tuple(
                ConstraintSpec.from_dict(_object(item, f"constraints[{index}]"))
                for index, item in enumerate(_array(mapping.get("constraints", []), "constraints"))
            ),
            balances=tuple(
                BalanceSpec.from_dict(_object(item, f"balances[{index}]"))
                for index, item in enumerate(_array(mapping.get("balances", []), "balances"))
            ),
            reset_mode=cast(ResetMode, reset_raw),
            timeout_s=timeout_s,
            metadata=metadata,
        )

    @property
    def reinitialize(self) -> bool:
        return self.reset_mode == "reinitialize"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_path": self.model_path,
            "registry_path": self.registry_path,
            "backend": self.backend,
            "writes": [asdict(item) for item in self.writes],
            "reads": [asdict(item) for item in self.reads],
            "constraints": [asdict(item) for item in self.constraints],
            "balances": [asdict(item) for item in self.balances],
            "reset_mode": self.reset_mode,
            "timeout_s": self.timeout_s,
            "metadata": dict(self.metadata),
        }

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
        mapping = _object(data, "evaluation result")

        def required_bool(name: str, default: bool | None = None) -> bool:
            if name not in mapping:
                if default is None:
                    raise ValueError(f"evaluation result is missing {name}")
                return default
            value = mapping[name]
            if not isinstance(value, bool):
                raise ValueError(f"result {name} must be a boolean")
            return value

        communication_ok = required_bool("communication_ok")
        engine_ok = required_bool("engine_ok", communication_ok)
        values = _object(mapping.get("values"), "result values")
        raw_units = _object(mapping.get("units"), "result units")
        units: dict[str, str | None] = {}
        for key, value in raw_units.items():
            if value is not None and not isinstance(value, str):
                raise ValueError("result unit values must be strings or null")
            units[str(key)] = value

        raw_violations = _array(mapping.get("violations"), "result violations")
        if not all(isinstance(item, str) for item in raw_violations):
            raise ValueError("result violations must contain only strings")
        violations = [str(item) for item in raw_violations]
        diagnostics = _object(mapping.get("diagnostics"), "result diagnostics")

        raw_balances = _object(
            mapping.get("balance_residuals", {}),
            "result balance_residuals",
        )
        balances: dict[str, dict[str, float]] = {}
        for name, raw_detail in raw_balances.items():
            detail = _object(raw_detail, f"result balance_residuals[{name}]")
            normalized_detail: dict[str, float] = {}
            for key, value in detail.items():
                normalized_detail[str(key)] = _finite_number(
                    value,
                    f"result balance_residuals[{name}].{key}",
                )
            balances[str(name)] = normalized_detail

        cache_source = mapping.get("cache_source", "computed")
        if cache_source not in {
            "computed",
            "persistent_cache",
            "same_batch_dedup",
            "inflight_singleflight",
        }:
            raise ValueError(f"Unsupported result cache_source: {cache_source}")
        cache_hit = mapping.get("cache_hit", cache_source != "computed")
        if not isinstance(cache_hit, bool):
            raise ValueError("result cache_hit must be a boolean")
        request_hash = mapping.get("request_hash", "")
        if not isinstance(request_hash, str):
            raise ValueError("result request_hash must be a string")
        worker_id = mapping.get("worker_id")
        if worker_id is not None and (
            isinstance(worker_id, bool) or not isinstance(worker_id, int)
        ):
            raise ValueError("result worker_id must be an integer or null")

        known = {
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
            "cache_source",
            "cache_hit",
            "request_hash",
            "worker_id",
        }
        unknown = sorted(set(mapping) - known)
        if unknown:
            raise ValueError(f"Unsupported evaluation result fields: {', '.join(unknown)}")

        return cls(
            ok=required_bool("ok"),
            communication_ok=communication_ok,
            engine_ok=engine_ok,
            converged=required_bool("converged"),
            feasible=required_bool("feasible"),
            values=values,
            units=units,
            violations=violations,
            diagnostics=diagnostics,
            elapsed_s=_nonnegative_number(mapping.get("elapsed_s"), "elapsed_s"),
            balance_residuals=balances,
            cache_source=cast(CacheSource, cache_source),
            cache_hit=cache_hit,
            request_hash=request_hash,
            worker_id=worker_id,
        )
