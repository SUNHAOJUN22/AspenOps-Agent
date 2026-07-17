from __future__ import annotations

import json
import math
import os
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from .batch import run_batch_document
from .config import Settings
from .optimizer import (
    Candidate,
    ParetoPoint,
    differential_evolution_batch,
    pareto_front,
)

if TYPE_CHECKING:
    from .pool_manager import PoolManager

VariableKind = Literal["continuous", "integer", "categorical", "ordinal"]
ObjectiveDirection = Literal["minimize", "maximize"]


class OptimizationCancelled(RuntimeError):
    pass


def _output_key(key: str, identifiers: dict[str, str]) -> str:
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
    choices: tuple[str | int | float | bool, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariableSpec:
        kind = str(data.get("kind", "continuous"))
        if kind not in {"continuous", "integer", "categorical", "ordinal"}:
            raise ValueError(f"Unsupported optimization variable kind: {kind}")
        choices = tuple(data.get("choices", []))
        lower = None if data.get("lower") is None else float(data["lower"])
        upper = None if data.get("upper") is None else float(data["upper"])
        if kind in {"categorical", "ordinal"}:
            if len(choices) < 2:
                raise ValueError(f"{kind} variable requires at least two choices")
        elif lower is None or upper is None or upper <= lower:
            raise ValueError(f"{kind} variable requires lower < upper")
        return cls(
            name=str(data.get("name", data["key"])),
            key=str(data["key"]),
            identifiers={str(key): str(value) for key, value in data.get("identifiers", {}).items()},
            kind=cast(VariableKind, kind),
            unit=None if data.get("unit") is None else str(data["unit"]),
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

    def decode(self, encoded: float) -> str | int | float | bool:
        lower, upper = self.bound()
        bounded = min(upper, max(lower, encoded))
        if self.kind == "continuous":
            return float(bounded)
        if self.kind == "integer":
            return int(round(bounded))
        index = int(round(bounded))
        return self.choices[index]

    def write(self, encoded: float) -> dict[str, Any]:
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObjectiveSpec:
        direction = str(data.get("direction", "minimize"))
        if direction not in {"minimize", "maximize"}:
            raise ValueError(f"Unsupported objective direction: {direction}")
        if "output_key" in data:
            output_key = str(data["output_key"])
        else:
            output_key = _output_key(
                str(data["key"]),
                {str(key): str(value) for key, value in data.get("identifiers", {}).items()},
            )
        weight = float(data.get("weight", 1.0))
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("Objective weight must be finite and positive")
        return cls(output_key, cast(ObjectiveDirection, direction), weight)

    def minimized_value(self, value: float) -> float:
        return value if self.direction == "minimize" else -value


@dataclass(frozen=True, slots=True)
class OptimizationBudget:
    population_size: int = 20
    generations: int = 40
    max_evaluations: int = 820
    mutation: float = 0.8
    crossover: float = 0.9
    seed: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OptimizationBudget:
        population_size = int(data.get("population_size", 20))
        generations = int(data.get("generations", 40))
        default_evaluations = population_size * (generations + 1)
        max_evaluations = int(data.get("max_evaluations", default_evaluations))
        if population_size < 4:
            raise ValueError("population_size must be at least four")
        if generations < 0 or max_evaluations < population_size:
            raise ValueError("Optimization budget is inconsistent")
        return cls(
            population_size=population_size,
            generations=generations,
            max_evaluations=max_evaluations,
            mutation=float(data.get("mutation", 0.8)),
            crossover=float(data.get("crossover", 0.9)),
            seed=int(data.get("seed", 0)),
        )


@dataclass(frozen=True, slots=True)
class OptimizationProblem:
    base_request: dict[str, Any]
    variables: tuple[VariableSpec, ...]
    objectives: tuple[ObjectiveSpec, ...]
    budget: OptimizationBudget
    checkpoint_path: Path | None = None

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> OptimizationProblem:
        raw = document.get("optimization")
        if not isinstance(raw, dict):
            raise ValueError("Optimization document requires an 'optimization' object")
        variables = tuple(VariableSpec.from_dict(item) for item in raw.get("variables", []))
        if not variables:
            raise ValueError("Optimization requires at least one variable")
        objective_items = raw.get("objectives")
        if objective_items is None and raw.get("objective") is not None:
            objective_items = [raw["objective"]]
        objectives = tuple(ObjectiveSpec.from_dict(item) for item in objective_items or [])
        if not objectives:
            raise ValueError("Optimization requires at least one objective")
        base_request = {key: value for key, value in document.items() if key != "optimization"}
        base_request.pop("points", None)
        checkpoint = raw.get("checkpoint_path")
        return cls(
            base_request=base_request,
            variables=variables,
            objectives=objectives,
            budget=OptimizationBudget.from_dict(dict(raw.get("budget", {}))),
            checkpoint_path=None if checkpoint is None else Path(str(checkpoint)).expanduser(),
        )

    def bounds(self) -> tuple[tuple[float, float], ...]:
        return tuple(variable.bound() for variable in self.variables)

    def decode(self, vector: Sequence[float]) -> dict[str, str | int | float | bool]:
        return {
            variable.name: variable.decode(value)
            for variable, value in zip(self.variables, vector, strict=True)
        }


@dataclass(frozen=True, slots=True)
class OptimizationTracePoint:
    x: tuple[float, ...]
    decoded: dict[str, str | int | float | bool]
    objectives: tuple[float, ...]
    minimized_objectives: tuple[float, ...]
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
    ) -> None:
        self.problem = problem
        self.settings = settings
        self.pool_manager = pool_manager
        self.cancel_check = cancel_check
        self.trace: list[OptimizationTracePoint] = []
        self.raw_results: list[dict[str, Any]] = []

    @staticmethod
    def _violation(result: dict[str, Any]) -> float:
        if bool(result.get("ok")):
            return 0.0
        diagnostics = result.get("diagnostics", {})
        total = float(diagnostics.get("total_constraint_violation", 0.0) or 0.0)
        balances = result.get("balance_residuals", {})
        total += sum(
            max(0.0, float(item.get("relative", 0.0)))
            for item in balances.values()
            if not bool(item.get("passed"))
        )
        violations = set(result.get("violations", []))
        if any(name.startswith("constraint_failed:") for name in violations):
            total += 1.0
        if any(name.startswith("balance_failed:") for name in violations):
            total += 1.0
        if not bool(result.get("communication_ok")):
            total += 1_000_000.0
        elif not bool(result.get("engine_ok")) or not bool(result.get("converged")):
            total += 100_000.0
        return max(total, 1e-12)

    def __call__(
        self,
        vectors: Sequence[tuple[float, ...]],
    ) -> Sequence[tuple[float, float]]:
        if self.cancel_check is not None and self.cancel_check():
            raise OptimizationCancelled("Optimization cancellation requested")
        points = [
            {
                "metadata": {"optimization_index": index},
                "writes": [
                    variable.write(value)
                    for variable, value in zip(
                        self.problem.variables,
                        vector,
                        strict=True,
                    )
                ],
            }
            for index, vector in enumerate(vectors)
        ]
        request = dict(self.problem.base_request)
        request["points"] = points
        results = run_batch_document(
            request,
            self.settings,
            pool_manager=self.pool_manager,
            cancel_check=self.cancel_check,
        )
        scores: list[tuple[float, float]] = []
        for vector, result in zip(vectors, results, strict=True):
            values = result.get("values", {})
            objective_values: list[float] = []
            minimized: list[float] = []
            missing = False
            for objective in self.problem.objectives:
                raw = values.get(objective.output_key)
                if raw is None:
                    missing = True
                    value = 1e12
                else:
                    value = float(raw)
                    if not math.isfinite(value):
                        missing = True
                        value = 1e12
                objective_values.append(value)
                minimized.append(objective.minimized_value(value))
            scalar = sum(
                objective.weight * value
                for objective, value in zip(
                    self.problem.objectives,
                    minimized,
                    strict=True,
                )
            )
            violation = self._violation(result)
            if missing:
                violation += 1_000_000.0
            trace = OptimizationTracePoint(
                x=tuple(vector),
                decoded=self.problem.decode(vector),
                objectives=tuple(objective_values),
                minimized_objectives=tuple(minimized),
                scalar_objective=scalar,
                violation=violation,
                ok=bool(result.get("ok")) and not missing,
                request_hash=str(result.get("request_hash", "")),
            )
            self.trace.append(trace)
            self.raw_results.append(result)
            scores.append((scalar, violation))
        return scores


def _write_checkpoint(
    path: Path,
    generation: int,
    population: tuple[Candidate, ...],
    evaluations: int,
) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "aspenops.optimization-checkpoint/v1",
        "generation": generation,
        "evaluations": evaluations,
        "population": [asdict(candidate) for candidate in population],
    }
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_optimization_document(
    document: dict[str, Any],
    settings: Settings,
    *,
    pool_manager: PoolManager | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    problem = OptimizationProblem.from_document(document)
    evaluator = _Evaluator(problem, settings, pool_manager, cancel_check)

    checkpoint: Callable[[int, tuple[Candidate, ...], int], None] | None = None
    if problem.checkpoint_path is not None:
        checkpoint = partial_checkpoint = lambda generation, population, evaluations: _write_checkpoint(
            problem.checkpoint_path,
            generation,
            population,
            evaluations,
        )
        del partial_checkpoint

    try:
        run = differential_evolution_batch(
            evaluator,
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
        status = "cancelled"
        run = None

    pareto_points = pareto_front(
        [
            ParetoPoint(point.x, point.minimized_objectives, point.violation)
            for point in evaluator.trace
        ]
    )
    trace_by_x = {point.x: point for point in evaluator.trace}
    pareto = [
        {
            "x": list(point.x),
            "decoded": trace_by_x[point.x].decoded,
            "objectives": list(trace_by_x[point.x].objectives),
            "violation": point.violation,
        }
        for point in pareto_points
    ]
    best = None
    if run is not None:
        best_trace = min(
            (
                point
                for point in evaluator.trace
                if point.x == run.best.x
            ),
            key=lambda point: (point.violation > 0, point.violation, point.scalar_objective),
        )
        best = {
            "x": list(run.best.x),
            "decoded": best_trace.decoded,
            "objectives": list(best_trace.objectives),
            "scalar_objective": run.best.objective,
            "violation": run.best.violation,
            "feasible": run.best.feasible,
        }
    return {
        "schema": "aspenops.optimization-result/v1",
        "status": status,
        "backend": problem.base_request.get("backend", settings.backend),
        "evaluations": len(evaluator.trace),
        "generations": 0 if run is None else run.generations,
        "best": best,
        "pareto": pareto,
        "variables": [asdict(variable) for variable in problem.variables],
        "objectives": [asdict(objective) for objective in problem.objectives],
        "budget": asdict(problem.budget),
        "qualification": (
            "control-plane-only"
            if problem.base_request.get("backend", settings.backend) == "mock"
            else "licensed-runtime-pending-engineering-review"
        ),
        "real_aspen_status": "PENDING_REAL_ASPEN_CERTIFICATION",
    }
