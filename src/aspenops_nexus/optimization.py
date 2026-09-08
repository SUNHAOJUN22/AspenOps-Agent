from __future__ import annotations

import json
import math
import os
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, cast

from .batch import run_batch_document
from .config import Settings
from .optimizer import (
    Candidate,
    DifferentialEvolutionResult,
    ParetoPoint,
    differential_evolution_batch,
    pareto_front,
)
from .policy import PolicyError
from .units import dimension as unit_dimension

if TYPE_CHECKING:
    from .pool import CasePool
    from .pool_manager import PoolManager

VariableKind = Literal["continuous", "integer", "categorical", "ordinal"]
ObjectiveDirection = Literal["minimize", "maximize"]
VariableValue: TypeAlias = str | int | float | bool
ObjectMap: TypeAlias = dict[str, object]


class OptimizationCancelled(RuntimeError):
    pass


def _object_map(value: object, *, label: str) -> ObjectMap:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    raw = cast(dict[object, object], value)
    return {str(key): item for key, item in raw.items()}


def _optional_object_map(value: object) -> ObjectMap:
    if not isinstance(value, dict):
        return {}
    raw = cast(dict[object, object], value)
    return {str(key): item for key, item in raw.items()}


def _object_sequence(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list | tuple):
        raise ValueError(f"{label} must be an array")
    return list(cast(Sequence[object], value))


def _required(data: Mapping[str, object], key: str) -> object:
    if key not in data:
        raise ValueError(f"Missing required optimization field: {key}")
    return data[key]


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _integer(value: object, *, label: str) -> int:
    number = _number(value, label=label)
    integer = int(number)
    if number != integer:
        raise ValueError(f"{label} must be an integer")
    return integer


def _choice(value: object) -> VariableValue:
    if isinstance(value, bool | str | int | float):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Optimization choices must be finite")
        return value
    raise ValueError(f"Optimization choices must be scalar JSON values, got {type(value).__name__}")


_MAX_FINITE = sys.float_info.max
_MAX_FINITE_FRACTION = Fraction.from_float(_MAX_FINITE)


def _finite_output(value: object) -> float | None:
    """Compatibility conversion for persisted result flags and diagnostics."""
    if not isinstance(value, bool | int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _strict_finite_output(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _saturating_nonnegative_add(total: float, value: float) -> float:
    normalized_total = max(0.0, total)
    normalized_value = max(0.0, value)
    if normalized_total >= _MAX_FINITE - normalized_value:
        return _MAX_FINITE
    return normalized_total + normalized_value


def _finite_weighted_sum(pairs: Sequence[tuple[float, float]]) -> float:
    materialized = tuple(pairs)
    terms: list[float] = []
    for weight, value in materialized:
        term = weight * value
        if not math.isfinite(term):
            break
        terms.append(term)
    else:
        try:
            total = math.fsum(terms)
        except OverflowError:
            pass
        else:
            if math.isfinite(total):
                return total
    exact = sum(
        (
            Fraction.from_float(weight) * Fraction.from_float(value)
            for weight, value in materialized
        ),
        Fraction(),
    )
    if exact > _MAX_FINITE_FRACTION:
        return _MAX_FINITE
    if exact < -_MAX_FINITE_FRACTION:
        return -_MAX_FINITE
    return float(exact)


def _output_key(key: str, identifiers: Mapping[str, str]) -> str:
    suffix = ",".join(f"{name}={value}" for name, value in sorted(identifiers.items()))
    return key if not suffix else f"{key}:{suffix}"


@dataclass(frozen=True, slots=True)
class VariableSpec:
    name: str
    key: str
    identifiers: dict[str, str]
    kind: VariableKind
    unit: str | None = None
    lower: float | None = None
    upper: float | None = None
    choices: tuple[VariableValue, ...] = ()

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> VariableSpec:
        key = _text(_required(data, "key"), label="variable key").strip()
        if not key:
            raise ValueError("variable key must not be empty")
        kind_text = _text(data.get("kind", "continuous"), label="variable kind").strip()
        if kind_text not in {"continuous", "integer", "categorical", "ordinal"}:
            raise ValueError(f"Unsupported optimization variable kind: {kind_text}")
        kind = cast(VariableKind, kind_text)

        identifiers_raw = _optional_object_map(data.get("identifiers", {}))
        identifiers = {name: str(value) for name, value in identifiers_raw.items()}
        unit_value = data.get("unit")
        unit = None if unit_value is None else _text(unit_value, label="variable unit")
        name = _text(data.get("name", key), label="variable name").strip()
        if not name:
            raise ValueError("variable name must not be empty")

        lower_value = data.get("lower")
        upper_value = data.get("upper")
        lower = None if lower_value is None else _number(lower_value, label="lower bound")
        upper = None if upper_value is None else _number(upper_value, label="upper bound")
        choices = tuple(
            _choice(item)
            for item in _object_sequence(data.get("choices", []), label="variable choices")
        )
        choice_identities = {(type(item).__name__, repr(item)) for item in choices}
        if len(choice_identities) != len(choices):
            raise ValueError("Optimization variable choices must be unique")

        if kind in {"categorical", "ordinal"}:
            if lower is not None or upper is not None:
                raise ValueError(f"{kind} variable cannot define numeric bounds")
            if len(choices) < 2:
                raise ValueError(f"{kind} variable requires at least two choices")
        else:
            if choices:
                raise ValueError(f"{kind} variable cannot define choices")
            if lower is None or upper is None or upper <= lower:
                raise ValueError(f"{kind} variable requires lower < upper")
            if kind == "integer" and (not lower.is_integer() or not upper.is_integer()):
                raise ValueError("integer bounds must be integral")

        return cls(
            name=name,
            key=key,
            identifiers=identifiers,
            kind=kind,
            unit=unit,
            lower=lower,
            upper=upper,
            choices=choices,
        )

    def bound(self) -> tuple[float, float]:
        if self.kind in {"categorical", "ordinal"}:
            return 0.0, float(len(self.choices) - 1)
        if self.lower is None or self.upper is None:
            raise ValueError(f"Variable {self.name} has no numeric bounds")
        return self.lower, self.upper

    def decode(self, encoded: float) -> VariableValue:
        lower, upper = self.bound()
        bounded = min(upper, max(lower, encoded))
        if self.kind == "continuous":
            return float(bounded)
        if self.kind == "integer":
            return int(round(bounded))
        return self.choices[int(round(bounded))]

    def write(self, encoded: float) -> dict[str, object]:
        return {
            "key": self.key,
            "identifiers": self.identifiers,
            "value": self.decode(encoded),
            "unit": self.unit,
        }


@dataclass(frozen=True, slots=True)
class ObjectiveSpec:
    output_key: str
    direction: ObjectiveDirection = "minimize"
    weight: float = 1.0
    unit: str | None = None
    dimension: str | None = None
    reference_value: float | None = None
    reference_scale: float | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> ObjectiveSpec:
        direction_value = data.get("direction", "minimize")
        direction_text = _text(direction_value, label="objective direction")
        if direction_text not in {"minimize", "maximize"}:
            raise ValueError(f"Unsupported objective direction: {direction_text}")
        direction = cast(ObjectiveDirection, direction_text)

        output_value = data.get("output_key")
        if output_value is not None:
            output_key = _text(output_value, label="objective output_key").strip()
        else:
            key = _text(_required(data, "key"), label="objective key").strip()
            identifiers_raw = _optional_object_map(data.get("identifiers", {}))
            identifiers = {name: str(value) for name, value in identifiers_raw.items()}
            output_key = _output_key(key, identifiers)
        if not output_key:
            raise ValueError("objective output_key must not be empty")

        weight_value = data.get("weight", 1.0)
        weight = _number(weight_value, label="objective weight")
        if weight <= 0:
            raise ValueError("Objective weight must be positive")

        normalization_names = ("unit", "dimension", "reference_value", "reference_scale")
        normalization_present = tuple(data.get(name) is not None for name in normalization_names)
        if any(normalization_present) and not all(normalization_present):
            raise ValueError(
                "Objective normalization requires unit, dimension, reference_value and "
                "reference_scale together"
            )

        unit: str | None = None
        declared_dimension: str | None = None
        reference_value: float | None = None
        reference_scale: float | None = None
        if all(normalization_present):
            unit = _text(data["unit"], label="objective unit").strip()
            declared_dimension = _text(data["dimension"], label="objective dimension").strip()
            if not unit or not declared_dimension:
                raise ValueError("Objective unit and dimension must not be empty")
            actual_dimension = unit_dimension(unit)
            if actual_dimension != declared_dimension:
                raise ValueError(
                    f"Objective unit {unit!r} has dimension {actual_dimension!r}, not "
                    f"{declared_dimension!r}"
                )
            reference_value = _number(data["reference_value"], label="objective reference_value")
            reference_scale = _number(data["reference_scale"], label="objective reference_scale")
            if reference_scale <= 0:
                raise ValueError("Objective reference_scale must be positive")

        return cls(
            output_key=output_key,
            direction=direction,
            weight=weight,
            unit=unit,
            dimension=declared_dimension,
            reference_value=reference_value,
            reference_scale=reference_scale,
        )

    @property
    def normalized(self) -> bool:
        return (
            self.unit is not None
            and self.dimension is not None
            and self.reference_value is not None
            and self.reference_scale is not None
        )

    def minimized_value(self, value: float) -> float:
        return value if self.direction == "minimize" else -value

    def scalarized_value(self, value: float) -> float:
        if not self.normalized:
            return self.minimized_value(value)
        assert self.reference_value is not None
        assert self.reference_scale is not None
        normalized = (value - self.reference_value) / self.reference_scale
        if not math.isfinite(normalized):
            raise ValueError("Objective normalization produced a non-finite value")
        return normalized if self.direction == "minimize" else -normalized


@dataclass(frozen=True, slots=True)
class OptimizationBudget:
    population_size: int = 20
    generations: int = 40
    max_evaluations: int = 820
    mutation: float = 0.8
    crossover: float = 0.9
    seed: int = 0

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> OptimizationBudget:
        population_size = _integer(data.get("population_size", 20), label="population_size")
        generations = _integer(data.get("generations", 40), label="generations")
        default_evaluations = population_size * (generations + 1)
        max_evaluations = _integer(
            data.get("max_evaluations", default_evaluations),
            label="max_evaluations",
        )
        mutation = _number(data.get("mutation", 0.8), label="mutation")
        crossover = _number(data.get("crossover", 0.9), label="crossover")
        seed = _integer(data.get("seed", 0), label="seed")
        if population_size < 4:
            raise ValueError("population_size must be at least four")
        if generations < 0 or max_evaluations < population_size:
            raise ValueError("Optimization budget is inconsistent")
        if mutation <= 0 or not 0 <= crossover <= 1:
            raise ValueError("Invalid mutation or crossover setting")
        return cls(
            population_size=population_size,
            generations=generations,
            max_evaluations=max_evaluations,
            mutation=mutation,
            crossover=crossover,
            seed=seed,
        )


@dataclass(frozen=True, slots=True)
class OptimizationProblem:
    base_request: ObjectMap
    variables: tuple[VariableSpec, ...]
    objectives: tuple[ObjectiveSpec, ...]
    budget: OptimizationBudget
    checkpoint_path: Path | None = None

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> OptimizationProblem:
        optimization = _object_map(_required(document, "optimization"), label="optimization")
        variable_items = _object_sequence(
            optimization.get("variables", []), label="optimization variables"
        )
        variables = tuple(
            VariableSpec.from_mapping(_object_map(item, label="optimization variable"))
            for item in variable_items
        )
        if not variables:
            raise ValueError("Optimization requires at least one variable")
        variable_names: set[str] = set()
        variable_targets: set[str] = set()
        for variable in variables:
            if variable.name in variable_names:
                raise ValueError(f"Duplicate optimization variable name: {variable.name}")
            variable_names.add(variable.name)
            target = _output_key(variable.key, variable.identifiers)
            if target in variable_targets:
                raise ValueError(f"Duplicate optimization variable target: {target}")
            variable_targets.add(target)

        objectives_value = optimization.get("objectives")
        if objectives_value is None and optimization.get("objective") is not None:
            objectives_value = [optimization["objective"]]
        objective_items = _object_sequence(
            objectives_value if objectives_value is not None else [],
            label="optimization objectives",
        )
        objectives = tuple(
            ObjectiveSpec.from_mapping(_object_map(item, label="optimization objective"))
            for item in objective_items
        )
        if not objectives:
            raise ValueError("Optimization requires at least one objective")
        objective_keys: set[str] = set()
        for objective in objectives:
            if objective.output_key in objective_keys:
                raise ValueError(f"Duplicate optimization objective: {objective.output_key}")
            objective_keys.add(objective.output_key)
        if len(objectives) > 1:
            unnormalized = [
                objective.output_key for objective in objectives if not objective.normalized
            ]
            if unnormalized:
                raise ValueError(
                    "Multi-objective weighted scalarization requires dimensionless "
                    "normalization for every objective; missing unit, dimension, "
                    "reference_value or reference_scale for: " + ", ".join(unnormalized)
                )

        base_request = {
            key: value for key, value in document.items() if key not in {"optimization", "points"}
        }
        reset_mode = base_request.get("reset_mode")
        if reset_mode == "warm_start" or base_request.get("reinitialize") is False:
            raise ValueError("Optimization requires reset_mode='reinitialize'")
        budget = OptimizationBudget.from_mapping(
            _optional_object_map(optimization.get("budget", {}))
        )
        checkpoint_value = optimization.get("checkpoint_path")
        checkpoint_path = (
            None
            if checkpoint_value is None
            else Path(_text(checkpoint_value, label="checkpoint_path")).expanduser()
        )
        return cls(
            base_request=base_request,
            variables=variables,
            objectives=objectives,
            budget=budget,
            checkpoint_path=checkpoint_path,
        )

    def validate_limits(self, settings: Settings) -> None:
        if len(self.variables) > settings.max_optimization_variables:
            raise ValueError(
                f"Optimization defines {len(self.variables)} variables; limit is "
                f"{settings.max_optimization_variables}"
            )
        if len(self.objectives) > settings.max_optimization_objectives:
            raise ValueError(
                f"Optimization defines {len(self.objectives)} objectives; limit is "
                f"{settings.max_optimization_objectives}"
            )
        if self.budget.max_evaluations > settings.max_optimization_evaluations:
            raise ValueError(
                f"Optimization evaluation budget {self.budget.max_evaluations} exceeds "
                f"limit {settings.max_optimization_evaluations}"
            )

    def checkpoint_for(self, settings: Settings) -> Path | None:
        if self.checkpoint_path is None:
            return None
        candidate = self.checkpoint_path
        resolved = (
            (settings.state_dir / candidate).expanduser().resolve()
            if not candidate.is_absolute()
            else candidate.expanduser().resolve()
        )
        roots = (settings.state_dir.expanduser().resolve(), *settings.allowed_roots)
        for root in roots:
            try:
                resolved.relative_to(root.expanduser().resolve())
                return resolved
            except ValueError:
                continue
        raise PolicyError(f"Optimization checkpoint path is outside allowed roots: {resolved}")

    def bounds(self) -> tuple[tuple[float, float], ...]:
        return tuple(variable.bound() for variable in self.variables)

    def scalarization_contract(self) -> dict[str, object]:
        dimensionless = all(objective.normalized for objective in self.objectives)
        return {
            "mode": (
                "dimensionless-affine-weighted-sum" if dimensionless else "single-objective-raw"
            ),
            "dimensionless": dimensionless,
            "formula": "sum(weight_i * sign_i * (value_i-reference_i)/scale_i)",
        }

    def decode(self, vector: Sequence[float]) -> dict[str, VariableValue]:
        return {
            variable.name: variable.decode(value)
            for variable, value in zip(self.variables, vector, strict=True)
        }


@dataclass(frozen=True, slots=True)
class OptimizationTracePoint:
    x: tuple[float, ...]
    decoded: dict[str, VariableValue]
    objectives: tuple[float, ...]
    minimized_objectives: tuple[float, ...]
    scalarized_objectives: tuple[float, ...]
    scalar_objective: float
    violation: float
    ok: bool
    request_hash: str


class _Evaluator:
    def __init__(
        self,
        problem: OptimizationProblem,
        settings: Settings,
        pool_manager: PoolManager | None,
        cancel_check: Callable[[], bool] | None,
        pool_observer: Callable[[CasePool | None], None] | None,
    ) -> None:
        self.problem = problem
        self.settings = settings
        self.pool_manager = pool_manager
        self.cancel_check = cancel_check
        self.pool_observer = pool_observer
        self.trace: list[OptimizationTracePoint] = []

    @staticmethod
    def _violation(result: Mapping[str, object]) -> float:
        if result.get("ok") is True:
            return 0.0
        diagnostics = _optional_object_map(result.get("diagnostics", {}))
        total_value = _finite_output(diagnostics.get("total_constraint_violation"))
        total = 0.0 if total_value is None else max(0.0, total_value)

        balances_value = result.get("balance_residuals", {})
        if isinstance(balances_value, dict):
            balances = cast(dict[object, object], balances_value)
            for balance_value in balances.values():
                balance = _optional_object_map(balance_value)
                if _finite_output(balance.get("passed")) != 1.0:
                    relative = _finite_output(balance.get("relative"))
                    if relative is not None:
                        total = _saturating_nonnegative_add(total, relative)

        violations_value = result.get("violations", [])
        if isinstance(violations_value, list | tuple | set):
            violations = {str(item) for item in cast(Sequence[object], violations_value)}
        else:
            violations = set()
        if any(name.startswith("constraint_failed:") for name in violations):
            total = _saturating_nonnegative_add(total, 1.0)
        if any(name.startswith("balance_failed:") for name in violations):
            total = _saturating_nonnegative_add(total, 1.0)
        if result.get("communication_ok") is not True:
            total = _saturating_nonnegative_add(total, 1_000_000.0)
        elif result.get("engine_ok") is not True or result.get("converged") is not True:
            total = _saturating_nonnegative_add(total, 100_000.0)
        return max(total, 1e-12)

    def evaluate_many(
        self,
        vectors: Sequence[tuple[float, ...]],
    ) -> Sequence[tuple[float, float]]:
        if self.cancel_check is not None and self.cancel_check():
            raise OptimizationCancelled("Optimization cancellation requested")
        points: list[dict[str, object]] = []
        for index, vector in enumerate(vectors):
            writes = [
                variable.write(value)
                for variable, value in zip(self.problem.variables, vector, strict=True)
            ]
            points.append(
                {
                    "metadata": {"optimization_index": index},
                    "writes": writes,
                }
            )

        request: ObjectMap = dict(self.problem.base_request)
        request["points"] = points
        results = run_batch_document(
            cast(dict[str, Any], request),
            self.settings,
            pool_manager=self.pool_manager,
            cancel_check=self.cancel_check,
            pool_observer=self.pool_observer,
        )
        scores: list[tuple[float, float]] = []
        for vector, raw_result in zip(vectors, results, strict=True):
            result = cast(Mapping[str, object], raw_result)
            values = _optional_object_map(result.get("values", {}))
            objective_values: list[float] = []
            minimized_values: list[float] = []
            scalarized_values: list[float] = []
            missing = False
            for objective in self.problem.objectives:
                value = _strict_finite_output(values.get(objective.output_key))
                if value is None:
                    missing = True
                    value = -1e12 if objective.direction == "maximize" else 1e12
                objective_values.append(value)
                minimized_values.append(objective.minimized_value(value))
                scalarized_values.append(objective.scalarized_value(value))
            scalar = _finite_weighted_sum(
                tuple(
                    (objective.weight, value)
                    for objective, value in zip(
                        self.problem.objectives,
                        scalarized_values,
                        strict=True,
                    )
                )
            )
            violation = self._violation(result)
            if missing:
                violation = _saturating_nonnegative_add(violation, 1_000_000.0)
            self.trace.append(
                OptimizationTracePoint(
                    x=tuple(vector),
                    decoded=self.problem.decode(vector),
                    objectives=tuple(objective_values),
                    minimized_objectives=tuple(minimized_values),
                    scalarized_objectives=tuple(scalarized_values),
                    scalar_objective=scalar,
                    violation=violation,
                    ok=result.get("ok") is True and not missing,
                    request_hash=str(result.get("request_hash", "")),
                )
            )
            scores.append((scalar, violation))
        return scores


def _write_checkpoint(
    path: Path,
    generation: int,
    population: tuple[Candidate, ...],
    evaluations: int,
) -> None:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "aspenops.optimization-checkpoint/v1",
        "generation": generation,
        "evaluations": evaluations,
        "population": [asdict(candidate) for candidate in population],
    }
    temporary = resolved.with_name(f".{resolved.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        os.replace(temporary, resolved)
    finally:
        temporary.unlink(missing_ok=True)


def _checkpoint_callback(
    path: Path,
) -> Callable[[int, tuple[Candidate, ...], int], None]:
    def callback(
        generation: int,
        population: tuple[Candidate, ...],
        evaluations: int,
    ) -> None:
        _write_checkpoint(path, generation, population, evaluations)

    return callback


def run_optimization_document(
    document: dict[str, Any],
    settings: Settings,
    *,
    pool_manager: PoolManager | None = None,
    cancel_check: Callable[[], bool] | None = None,
    pool_observer: Callable[[CasePool | None], None] | None = None,
) -> dict[str, Any]:
    normalized_document: ObjectMap = {str(key): value for key, value in document.items()}
    problem = OptimizationProblem.from_document(normalized_document)
    problem.validate_limits(settings)
    evaluator = _Evaluator(problem, settings, pool_manager, cancel_check, pool_observer)
    checkpoint_path = problem.checkpoint_for(settings)
    checkpoint = None if checkpoint_path is None else _checkpoint_callback(checkpoint_path)

    run: DifferentialEvolutionResult | None
    try:
        run = differential_evolution_batch(
            evaluator.evaluate_many,
            problem.bounds(),
            population_size=problem.budget.population_size,
            generations=problem.budget.generations,
            mutation=problem.budget.mutation,
            crossover=problem.budget.crossover,
            seed=problem.budget.seed,
            max_evaluations=problem.budget.max_evaluations,
            checkpoint=checkpoint,
        )
        status = "completed"
    except OptimizationCancelled:
        run = None
        status = "cancelled"

    pareto_points = pareto_front(
        [
            ParetoPoint(point.x, point.minimized_objectives, point.violation)
            for point in evaluator.trace
        ]
    )

    def matching_trace(point: ParetoPoint) -> OptimizationTracePoint:
        matches = [
            item
            for item in evaluator.trace
            if item.x == point.x
            and item.minimized_objectives == point.objectives
            and item.violation == point.violation
        ]
        if not matches:
            raise RuntimeError("Pareto point has no exact optimization trace record")
        return matches[-1]

    pareto = []
    for point in pareto_points:
        trace = matching_trace(point)
        pareto.append(
            {
                "x": list(point.x),
                "decoded": trace.decoded,
                "objectives": list(trace.objectives),
                "scalarized_objectives": list(trace.scalarized_objectives),
                "violation": point.violation,
            }
        )

    best: dict[str, object] | None = None
    if run is not None:
        matching = [point for point in evaluator.trace if point.x == run.best.x]
        if not matching:
            raise RuntimeError("Optimization best candidate has no trace record")
        best_trace = min(
            matching,
            key=lambda point: (
                point.violation > 0,
                point.violation,
                point.scalar_objective,
            ),
        )
        best = {
            "x": list(run.best.x),
            "decoded": best_trace.decoded,
            "objectives": list(best_trace.objectives),
            "scalarized_objectives": list(best_trace.scalarized_objectives),
            "scalar_objective": run.best.objective,
            "violation": run.best.violation,
            "feasible": run.best.feasible,
        }

    backend = problem.base_request.get("backend", settings.backend)
    qualification = (
        "control-plane-only" if backend == "mock" else "licensed-runtime-pending-engineering-review"
    )
    return {
        "schema": "aspenops.optimization-result/v1",
        "status": status,
        "backend": backend,
        "evaluations": len(evaluator.trace),
        "generations": 0 if run is None else run.generations,
        "best": best,
        "pareto": pareto,
        "variables": [asdict(variable) for variable in problem.variables],
        "objectives": [asdict(objective) for objective in problem.objectives],
        "scalarization": problem.scalarization_contract(),
        "budget": asdict(problem.budget),
        "qualification": qualification,
        "real_aspen_status": "PENDING_REAL_ASPEN_CERTIFICATION",
    }
