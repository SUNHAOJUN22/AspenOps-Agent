from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.config import Settings
from aspenops_nexus.optimization import OptimizationProblem, VariableSpec, run_optimization_document
from aspenops_nexus.policy import PolicyError

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def variable(
    name: str,
    *,
    key: str = "stream.input.temperature",
    stream: str = "FEED",
) -> dict[str, Any]:
    return {
        "name": name,
        "key": key,
        "identifiers": {"stream": stream},
        "kind": "continuous",
        "lower": 60,
        "upper": 120,
        "unit": "C",
    }


def objective(output_key: str = "stream.output.purity:stream=PRODUCT") -> dict[str, Any]:
    return {"output_key": output_key, "direction": "maximize"}


def optimization_document() -> dict[str, Any]:
    return {
        "backend": "mock",
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
        "workers": 1,
        "reads": [
            {
                "key": "stream.output.purity",
                "identifiers": {"stream": "PRODUCT"},
                "unit": "fraction",
            }
        ],
        "optimization": {
            "variables": [variable("temperature")],
            "objectives": [objective()],
            "budget": {
                "population_size": 4,
                "generations": 0,
                "max_evaluations": 4,
                "seed": 3,
            },
        },
    }


def test_problem_rejects_duplicate_variable_names_targets_and_objectives() -> None:
    duplicate_names = optimization_document()
    duplicate_names["optimization"]["variables"] = [
        variable("same", stream="A"),
        variable("same", stream="B"),
    ]
    with pytest.raises(ValueError, match="Duplicate optimization variable name: same"):
        OptimizationProblem.from_document(duplicate_names)

    duplicate_targets = optimization_document()
    duplicate_targets["optimization"]["variables"] = [
        variable("first"),
        variable("second"),
    ]
    with pytest.raises(ValueError, match="Duplicate optimization variable target"):
        OptimizationProblem.from_document(duplicate_targets)

    duplicate_objectives = optimization_document()
    duplicate_objectives["optimization"]["objectives"] = [objective(), objective()]
    with pytest.raises(ValueError, match="Duplicate optimization objective"):
        OptimizationProblem.from_document(duplicate_objectives)


def test_variable_contract_rejects_ambiguous_domains() -> None:
    with pytest.raises(ValueError, match="variable key must not be empty"):
        VariableSpec.from_mapping({"key": " ", "kind": "continuous", "lower": 0, "upper": 1})
    with pytest.raises(ValueError, match="variable name must not be empty"):
        VariableSpec.from_mapping(
            {"name": " ", "key": "x", "kind": "continuous", "lower": 0, "upper": 1}
        )
    with pytest.raises(ValueError, match="integer bounds must be integral"):
        VariableSpec.from_mapping(
            {"key": "x", "kind": "integer", "lower": 1.5, "upper": 4}
        )
    with pytest.raises(ValueError, match="choices must be unique"):
        VariableSpec.from_mapping(
            {"key": "x", "kind": "categorical", "choices": ["a", "a"]}
        )
    with pytest.raises(ValueError, match="cannot define numeric bounds"):
        VariableSpec.from_mapping(
            {
                "key": "x",
                "kind": "ordinal",
                "choices": ["low", "high"],
                "lower": 0,
                "upper": 1,
            }
        )
    with pytest.raises(ValueError, match="cannot define choices"):
        VariableSpec.from_mapping(
            {
                "key": "x",
                "kind": "continuous",
                "lower": 0,
                "upper": 1,
                "choices": [0, 1],
            }
        )


def test_optimization_enforces_configured_problem_limits(tmp_path: Path) -> None:
    too_many_evaluations = optimization_document()
    too_many_evaluations["optimization"]["budget"]["max_evaluations"] = 8
    with pytest.raises(ValueError, match="evaluation budget 8 exceeds limit 4"):
        run_optimization_document(
            too_many_evaluations,
            Settings(state_dir=tmp_path, max_optimization_evaluations=4),
        )

    too_many_variables = optimization_document()
    too_many_variables["optimization"]["variables"] = [
        variable("first", stream="A"),
        variable("second", stream="B"),
    ]
    with pytest.raises(ValueError, match="2 variables; limit is 1"):
        run_optimization_document(
            too_many_variables,
            Settings(state_dir=tmp_path, max_optimization_variables=1),
        )

    too_many_objectives = optimization_document()
    too_many_objectives["optimization"]["objectives"] = [
        objective(),
        objective("block.output.reboiler_duty:block=COL1"),
    ]
    with pytest.raises(ValueError, match="2 objectives; limit is 1"):
        run_optimization_document(
            too_many_objectives,
            Settings(state_dir=tmp_path, max_optimization_objectives=1),
        )


def test_relative_checkpoint_is_confined_to_state_directory(tmp_path: Path) -> None:
    request = optimization_document()
    request["optimization"]["checkpoint_path"] = "checkpoints/latest.json"
    state_dir = tmp_path / "state"
    result = run_optimization_document(request, Settings(state_dir=state_dir))
    assert result["status"] == "completed"
    assert (state_dir / "checkpoints/latest.json").is_file()


def test_absolute_checkpoint_outside_state_or_allowed_roots_is_rejected(tmp_path: Path) -> None:
    request = optimization_document()
    request["optimization"]["checkpoint_path"] = str(tmp_path / "outside.json")
    with pytest.raises(PolicyError, match="checkpoint path is outside"):
        run_optimization_document(
            request,
            Settings(state_dir=tmp_path / "state"),
        )

    allowed = tmp_path / "allowed"
    request["optimization"]["checkpoint_path"] = str(allowed / "checkpoint.json")
    result = run_optimization_document(
        request,
        Settings(state_dir=tmp_path / "state", allowed_roots=(allowed,)),
    )
    assert result["status"] == "completed"
    assert (allowed / "checkpoint.json").is_file()


def test_missing_maximize_output_has_worst_internal_objective(tmp_path: Path) -> None:
    request = optimization_document()
    request["optimization"]["objectives"] = [
        {"output_key": "missing.output", "direction": "maximize"}
    ]
    result = run_optimization_document(request, Settings(state_dir=tmp_path))
    assert result["status"] == "completed"
    assert result["best"]["feasible"] is False
    assert result["best"]["scalar_objective"] == 1e12
