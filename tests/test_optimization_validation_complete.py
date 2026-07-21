from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus import optimization as optimization_module
from aspenops_nexus.config import Settings
from aspenops_nexus.optimization import (
    ObjectiveSpec,
    OptimizationBudget,
    OptimizationCancelled,
    OptimizationProblem,
    VariableSpec,
)
from aspenops_nexus.optimizer import Candidate, DifferentialEvolutionResult


def minimal_document() -> dict[str, Any]:
    return {
        "backend": "mock",
        "model_path": "model.json",
        "registry_path": "registry.json",
        "points": [{"ignored": True}],
        "optimization": {
            "variables": [
                {
                    "name": "temperature",
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "kind": "continuous",
                    "lower": 10,
                    "upper": 20,
                    "unit": "C",
                }
            ],
            "objectives": [
                {
                    "output_key": "objective",
                    "direction": "minimize",
                }
            ],
            "budget": {
                "population_size": 4,
                "generations": 0,
                "max_evaluations": 4,
            },
        },
    }


def test_object_mapping_and_sequence_helpers_validate_shapes() -> None:
    assert optimization_module._object_map({1: "value"}, label="value") == {"1": "value"}
    with pytest.raises(ValueError, match="value must be an object"):
        optimization_module._object_map([], label="value")

    assert optimization_module._optional_object_map({1: 2}) == {"1": 2}
    assert optimization_module._optional_object_map(None) == {}
    assert optimization_module._object_sequence((1, 2), label="items") == [1, 2]
    with pytest.raises(ValueError, match="items must be an array"):
        optimization_module._object_sequence("not-an-array", label="items")
    with pytest.raises(ValueError, match="Missing required optimization field"):
        optimization_module._required({}, "missing")


def test_scalar_validation_helpers_reject_ambiguous_values() -> None:
    assert optimization_module._text("value", label="field") == "value"
    with pytest.raises(ValueError, match="field must be a string"):
        optimization_module._text(1, label="field")

    assert optimization_module._number(2, label="field") == 2.0
    for value in (True, "2"):
        with pytest.raises(ValueError, match="field must be numeric"):
            optimization_module._number(value, label="field")
    with pytest.raises(ValueError, match="field must be finite"):
        optimization_module._number(float("inf"), label="field")

    assert optimization_module._integer(2.0, label="field") == 2
    with pytest.raises(ValueError, match="field must be an integer"):
        optimization_module._integer(2.5, label="field")

    for value in (True, "mode", 2, 2.5):
        assert optimization_module._choice(value) == value
    with pytest.raises(ValueError, match="choices must be finite"):
        optimization_module._choice(float("nan"))
    with pytest.raises(ValueError, match="scalar JSON values"):
        optimization_module._choice(["not", "scalar"])

    assert optimization_module._finite_output(True) == 1.0
    assert optimization_module._finite_output(2.5) == 2.5
    assert optimization_module._finite_output(float("nan")) is None
    assert optimization_module._finite_output("2.5") is None
    assert optimization_module._output_key("key", {}) == "key"
    assert optimization_module._output_key("key", {"z": "2", "a": "1"}) == ("key:a=1,z=2")


def test_variable_spec_clamps_decodes_and_emits_writes() -> None:
    continuous = VariableSpec.from_mapping(
        {
            "name": "temperature",
            "key": "temperature",
            "identifiers": {"stream": "FEED"},
            "kind": "continuous",
            "lower": 10,
            "upper": 20,
            "unit": "C",
        }
    )
    assert continuous.bound() == (10.0, 20.0)
    assert continuous.decode(5.0) == 10.0
    assert continuous.decode(25.0) == 20.0
    assert continuous.write(15.0) == {
        "key": "temperature",
        "identifiers": {"stream": "FEED"},
        "value": 15.0,
        "unit": "C",
    }

    integer = VariableSpec.from_mapping(
        {
            "key": "stages",
            "kind": "integer",
            "lower": 2,
            "upper": 10,
        }
    )
    assert integer.decode(7.6) == 8
    assert integer.decode(-100.0) == 2

    categorical = VariableSpec.from_mapping(
        {
            "key": "mode",
            "kind": "categorical",
            "choices": ["a", "b", "c"],
        }
    )
    assert categorical.bound() == (0.0, 2.0)
    assert categorical.decode(-10.0) == "a"
    assert categorical.decode(99.0) == "c"


def test_variable_spec_rejects_invalid_fields_and_missing_bounds() -> None:
    with pytest.raises(ValueError, match="variable key must be a string"):
        VariableSpec.from_mapping({"key": 1})
    with pytest.raises(ValueError, match="variable kind must be a string"):
        VariableSpec.from_mapping({"key": "x", "kind": 1})
    with pytest.raises(ValueError, match="variable unit must be a string"):
        VariableSpec.from_mapping(
            {"key": "x", "kind": "continuous", "lower": 0, "upper": 1, "unit": 1}
        )
    with pytest.raises(ValueError, match="variable name must be a string"):
        VariableSpec.from_mapping(
            {"key": "x", "name": 1, "kind": "continuous", "lower": 0, "upper": 1}
        )
    with pytest.raises(ValueError, match="lower bound must be numeric"):
        VariableSpec.from_mapping({"key": "x", "kind": "continuous", "lower": "0", "upper": 1})
    with pytest.raises(ValueError, match="variable choices must be an array"):
        VariableSpec.from_mapping({"key": "x", "kind": "categorical", "choices": "a"})
    with pytest.raises(ValueError, match="choices must be finite"):
        VariableSpec.from_mapping(
            {"key": "x", "kind": "categorical", "choices": ["a", float("inf")]}
        )

    incomplete = VariableSpec(
        name="x",
        key="x",
        identifiers={},
        kind="continuous",
    )
    with pytest.raises(ValueError, match="has no numeric bounds"):
        incomplete.bound()


def test_objective_spec_builds_output_key_and_validates_weight() -> None:
    objective = ObjectiveSpec.from_mapping(
        {
            "key": "purity",
            "identifiers": {"stream": "PRODUCT", "phase": "MIXED"},
            "direction": "maximize",
            "weight": 2,
        }
    )
    assert objective.output_key == "purity:phase=MIXED,stream=PRODUCT"
    assert objective.minimized_value(0.9) == -0.9
    minimize = ObjectiveSpec.from_mapping({"output_key": "duty"})
    assert minimize.minimized_value(10.0) == 10.0

    with pytest.raises(ValueError, match="objective output_key must be a string"):
        ObjectiveSpec.from_mapping({"output_key": 1})
    with pytest.raises(ValueError, match="objective key must be a string"):
        ObjectiveSpec.from_mapping({"key": 1})
    with pytest.raises(ValueError, match="objective weight must be numeric"):
        ObjectiveSpec.from_mapping({"output_key": "x", "weight": True})


def test_optimization_budget_rejects_every_invalid_dimension() -> None:
    budget = OptimizationBudget.from_mapping(
        {"population_size": 4, "generations": 2, "mutation": 0.5, "crossover": 0.2}
    )
    assert budget.max_evaluations == 12

    invalid_cases = [
        ({"population_size": 4.5}, "population_size must be an integer"),
        ({"population_size": 4, "generations": -1}, "budget is inconsistent"),
        (
            {"population_size": 4, "generations": 1, "max_evaluations": 3},
            "budget is inconsistent",
        ),
        ({"population_size": 4, "mutation": 0}, "Invalid mutation"),
        ({"population_size": 4, "crossover": -0.1}, "Invalid mutation"),
        ({"population_size": 4, "crossover": 1.1}, "Invalid mutation"),
    ]
    for data, message in invalid_cases:
        with pytest.raises(ValueError, match=message):
            OptimizationBudget.from_mapping(data)


def test_problem_parsing_supports_singular_objective_and_checkpoint(tmp_path: Path) -> None:
    document = minimal_document()
    optimization = document["optimization"]
    optimization["objective"] = optimization.pop("objectives")[0]
    optimization["checkpoint_path"] = str(tmp_path / "checkpoint.json")
    problem = OptimizationProblem.from_document(document)
    assert problem.base_request == {
        "backend": "mock",
        "model_path": "model.json",
        "registry_path": "registry.json",
    }
    assert problem.checkpoint_path == tmp_path / "checkpoint.json"
    assert problem.bounds() == ((10.0, 20.0),)
    assert problem.decode((15.0,)) == {"temperature": 15.0}
    with pytest.raises(ValueError):
        problem.decode((15.0, 16.0))


def test_problem_parsing_rejects_malformed_nested_values() -> None:
    with pytest.raises(ValueError, match="optimization must be an object"):
        OptimizationProblem.from_document({"optimization": []})
    with pytest.raises(ValueError, match="optimization variables must be an array"):
        OptimizationProblem.from_document({"optimization": {"variables": "bad"}})
    with pytest.raises(ValueError, match="optimization variable must be an object"):
        OptimizationProblem.from_document(
            {"optimization": {"variables": [1], "objectives": [{"output_key": "x"}]}}
        )
    document = minimal_document()
    document["optimization"]["objectives"] = "bad"
    with pytest.raises(ValueError, match="optimization objectives must be an array"):
        OptimizationProblem.from_document(document)
    document = minimal_document()
    document["optimization"]["objectives"] = [1]
    with pytest.raises(ValueError, match="optimization objective must be an object"):
        OptimizationProblem.from_document(document)
    document = minimal_document()
    document["optimization"]["checkpoint_path"] = 1
    with pytest.raises(ValueError, match="checkpoint_path must be a string"):
        OptimizationProblem.from_document(document)


def evaluator(tmp_path: Path) -> optimization_module._Evaluator:
    return optimization_module._Evaluator(
        OptimizationProblem.from_document(minimal_document()),
        Settings(state_dir=tmp_path),
        None,
        None,
        None,
    )


def test_evaluator_violation_accounts_for_all_failure_classes(tmp_path: Path) -> None:
    active = evaluator(tmp_path)
    assert active._violation({"ok": True}) == 0.0

    violation = active._violation(
        {
            "ok": False,
            "communication_ok": False,
            "engine_ok": False,
            "converged": False,
            "diagnostics": {"total_constraint_violation": 2.0},
            "balance_residuals": {
                "mass": {"passed": False, "relative": 0.5},
                "ignored": {"passed": True, "relative": 100.0},
                "nonfinite": {"passed": False, "relative": float("nan")},
                "malformed": "not-an-object",
            },
            "violations": ["constraint_failed:x", "balance_failed:mass"],
        }
    )
    assert violation == pytest.approx(1_000_004.5)

    engine_failure = active._violation(
        {
            "ok": False,
            "communication_ok": True,
            "engine_ok": False,
            "converged": False,
            "violations": "not-a-sequence",
            "balance_residuals": [],
        }
    )
    assert engine_failure == pytest.approx(100_000.0)
    assert active._violation(
        {
            "ok": False,
            "communication_ok": True,
            "engine_ok": True,
            "converged": True,
        }
    ) == pytest.approx(1e-12)


def test_evaluator_cancellation_is_checked_before_batch(tmp_path: Path) -> None:
    active = optimization_module._Evaluator(
        OptimizationProblem.from_document(minimal_document()),
        Settings(state_dir=tmp_path),
        None,
        lambda: True,
        None,
    )
    with pytest.raises(OptimizationCancelled, match="cancellation requested"):
        active.evaluate_many([(15.0,)])


def test_evaluator_builds_points_scores_and_missing_output_penalties(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = minimal_document()
    document["optimization"]["objectives"] = [
        {"output_key": "first", "direction": "minimize", "weight": 1},
        {"output_key": "second", "direction": "maximize", "weight": 2},
    ]
    problem = OptimizationProblem.from_document(document)
    observed: dict[str, Any] = {}

    def run_batch(
        request: dict[str, Any],
        settings: Settings,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        observed["request"] = request
        observed["settings"] = settings
        observed["kwargs"] = kwargs
        return [
            {
                "ok": True,
                "communication_ok": True,
                "engine_ok": True,
                "converged": True,
                "values": {"first": 3.0, "second": 2.0},
                "request_hash": "hash-1",
            },
            {
                "ok": False,
                "communication_ok": True,
                "engine_ok": True,
                "converged": True,
                "values": {"first": float("nan")},
                "request_hash": "hash-2",
            },
        ]

    monkeypatch.setattr(optimization_module, "run_batch_document", run_batch)
    settings = Settings(state_dir=tmp_path)
    active = optimization_module._Evaluator(problem, settings, None, None, None)
    scores = active.evaluate_many([(12.0,), (18.0,)])

    assert observed["request"]["points"] == [
        {
            "metadata": {"optimization_index": 0},
            "writes": [problem.variables[0].write(12.0)],
        },
        {
            "metadata": {"optimization_index": 1},
            "writes": [problem.variables[0].write(18.0)],
        },
    ]
    assert observed["settings"] is settings
    assert scores[0] == pytest.approx((-1.0, 0.0))
    assert scores[1][1] >= 1_000_000.0
    assert active.trace[0].decoded == {"temperature": 12.0}
    assert active.trace[0].objectives == (3.0, 2.0)
    assert active.trace[0].minimized_objectives == (3.0, -2.0)
    assert active.trace[0].request_hash == "hash-1"
    assert active.trace[0].ok is True
    assert active.trace[1].ok is False
    assert active.trace[1].objectives == (1e12, -1e12)


def test_run_optimization_rejects_untraced_best_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = Candidate((15.0,), 1.0, 0.0)
    monkeypatch.setattr(
        optimization_module,
        "differential_evolution_batch",
        lambda *args, **kwargs: DifferentialEvolutionResult(
            best=candidate,
            population=(candidate,),
            evaluations=1,
            generations=0,
        ),
    )
    with pytest.raises(RuntimeError, match="no trace record"):
        optimization_module.run_optimization_document(
            minimal_document(),
            Settings(state_dir=tmp_path),
        )


def test_cancelled_nonmock_optimization_keeps_certification_boundary(tmp_path: Path) -> None:
    document = minimal_document()
    document["backend"] = "hysys"
    result = optimization_module.run_optimization_document(
        document,
        Settings(state_dir=tmp_path, backend="hysys"),
        cancel_check=lambda: True,
    )
    assert result["status"] == "cancelled"
    assert result["qualification"] == "licensed-runtime-pending-engineering-review"
    assert result["real_aspen_status"] == "PENDING_REAL_ASPEN_CERTIFICATION"
    assert result["best"] is None
    assert result["generations"] == 0
