from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_optimization import document

from aspenops_nexus.config import Settings
from aspenops_nexus.optimization import (
    ObjectiveSpec,
    OptimizationBudget,
    OptimizationProblem,
    VariableSpec,
    run_optimization_document,
)


def test_variable_kinds_decode_and_validate() -> None:
    integer = VariableSpec.from_mapping(
        {
            "name": "stages",
            "key": "block.input.stages",
            "identifiers": {"block": "C1"},
            "kind": "integer",
            "lower": 10,
            "upper": 30,
            "unit": "1",
        }
    )
    category = VariableSpec.from_mapping(
        {
            "name": "mode",
            "key": "mode",
            "kind": "categorical",
            "choices": ["a", "b", "c"],
        }
    )
    assert integer.decode(19.6) == 20
    assert category.decode(1.7) == "c"
    with pytest.raises(ValueError, match="Unsupported"):
        VariableSpec.from_mapping({"key": "x", "kind": "invalid"})
    with pytest.raises(ValueError, match="at least two choices"):
        VariableSpec.from_mapping({"key": "x", "kind": "categorical", "choices": ["only"]})
    with pytest.raises(ValueError, match="lower < upper"):
        VariableSpec.from_mapping({"key": "x", "kind": "continuous", "lower": 2, "upper": 1})


def test_objective_and_budget_validation() -> None:
    maximize = ObjectiveSpec.from_mapping(
        {"output_key": "purity", "direction": "maximize", "weight": 2}
    )
    assert maximize.minimized_value(0.9) == -0.9
    with pytest.raises(ValueError, match="direction"):
        ObjectiveSpec.from_mapping({"output_key": "x", "direction": "sideways"})
    with pytest.raises(ValueError, match="positive"):
        ObjectiveSpec.from_mapping({"output_key": "x", "weight": 0})
    with pytest.raises(ValueError, match="at least four"):
        OptimizationBudget.from_mapping({"population_size": 3})
    with pytest.raises(ValueError, match="inconsistent"):
        OptimizationBudget.from_mapping(
            {"population_size": 4, "generations": 3, "max_evaluations": 3}
        )


def test_problem_requires_variables_and_objectives() -> None:
    with pytest.raises(ValueError, match="optimization"):
        OptimizationProblem.from_document({})
    with pytest.raises(ValueError, match="variable"):
        OptimizationProblem.from_document({"optimization": {"objectives": [{}]}})
    with pytest.raises(ValueError, match="objective"):
        OptimizationProblem.from_document(
            {
                "optimization": {
                    "variables": [
                        {
                            "key": "x",
                            "kind": "continuous",
                            "lower": 0,
                            "upper": 1,
                        }
                    ]
                }
            }
        )


def test_optimization_honors_cancellation_before_first_batch(tmp_path: Path) -> None:
    result = run_optimization_document(
        document(),
        Settings(state_dir=tmp_path, max_workers=1, license_slots=1),
        cancel_check=lambda: True,
    )
    assert result["status"] == "cancelled"
    assert result["evaluations"] == 0
    assert result["best"] is None


def test_optimization_writes_atomic_checkpoint(tmp_path: Path) -> None:
    request = document()
    checkpoint = tmp_path / "checkpoint.json"
    request["optimization"]["checkpoint_path"] = str(checkpoint)
    request["optimization"]["budget"] = {
        "population_size": 4,
        "generations": 0,
        "max_evaluations": 4,
        "seed": 5,
    }
    result = run_optimization_document(
        request,
        Settings(state_dir=tmp_path / "state", max_workers=1, license_slots=1),
    )
    assert result["status"] == "completed"
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["generation"] == 0
    assert payload["evaluations"] == 4
    assert len(payload["population"]) == 4
    assert not list(tmp_path.glob(".*.tmp"))


def test_missing_objective_output_is_finite_infeasible(tmp_path: Path) -> None:
    request = document()
    request["optimization"]["objectives"] = [
        {"output_key": "not.declared.in.results", "direction": "minimize"}
    ]
    request["optimization"]["budget"] = {
        "population_size": 4,
        "generations": 0,
        "max_evaluations": 4,
    }
    result = run_optimization_document(
        request,
        Settings(state_dir=tmp_path, max_workers=1, license_slots=1),
    )
    assert result["status"] == "completed"
    assert result["best"]["feasible"] is False
    assert result["best"]["violation"] >= 1_000_000
