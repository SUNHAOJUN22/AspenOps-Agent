from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.evaluation_plan import EvaluationPlanCompiler
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.registry import NodeRegistry

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [
                {
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "value": 100.0,
                    "unit": "C",
                }
            ],
            "reads": [
                {
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "unit": "C",
                }
            ],
            "constraints": [
                {
                    "key": "reactor.output.conversion",
                    "identifiers": {"block": "R1"},
                    "operator": ">=",
                    "value": 0.5,
                    "unit": "fraction",
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "change",
    ["write_value", "write_unit", "write_target", "reads", "required", "constraint", "reset"],
)
def test_precompiled_plan_mismatch_fails_before_backend_operations(change: str) -> None:
    original = request()
    registry = NodeRegistry(REGISTRY)
    plan = EvaluationPlanCompiler.compile(registry, original)
    if change == "write_value":
        changed = replace(original, writes=(replace(original.writes[0], value=50.0),))
    elif change == "write_unit":
        changed = replace(original, writes=(replace(original.writes[0], unit="K"),))
    elif change == "write_target":
        changed = replace(
            original, writes=(replace(original.writes[0], identifiers={"stream": "OTHER"}),)
        )
    elif change == "reads":
        changed = replace(original, reads=())
    elif change == "required":
        changed = replace(original, reads=(replace(original.reads[0], required=False),))
    elif change == "constraint":
        changed = replace(original, constraints=(replace(original.constraints[0], value=0.99),))
    else:
        changed = replace(
            original,
            reset_mode="warm_start",
            metadata={"warm_start_session": "plan-binding-test", "warm_start_step": 0},
        )
    backend = Mock(spec=MockBackend)
    result = evaluate(backend, registry, changed, plan=plan)
    assert not result.ok and not result.feasible
    assert not result.engine_ok and not result.communication_ok
    assert result.diagnostics["exception_type"] == "ValueError"
    assert "plan does not match request semantics" in result.diagnostics["exception"]
    assert result.diagnostics["state_trace"] == ["received", "failed"]
    assert backend.mock_calls == []


def test_boolean_is_not_equal_to_a_compiled_numeric_input() -> None:
    original = request()
    original = replace(original, writes=(replace(original.writes[0], value=1),))
    registry = NodeRegistry(REGISTRY)
    plan = EvaluationPlanCompiler.compile(registry, original)
    changed = replace(original, writes=(replace(original.writes[0], value=True),))
    # Plain dictionary equality would miss this type-changing mismatch.
    assert plan.physical_identity == changed.physical_identity()
    backend = Mock(spec=MockBackend)
    result = evaluate(backend, registry, changed, plan=plan)
    assert not result.ok
    assert "plan does not match request semantics" in result.diagnostics["exception"]
    assert backend.mock_calls == []


def test_nested_request_mutation_invalidates_the_precompiled_snapshot() -> None:
    original = request()
    registry = NodeRegistry(REGISTRY)
    plan = EvaluationPlanCompiler.compile(registry, original)
    original.writes[0].identifiers["stream"] = "OTHER"
    backend = Mock(spec=MockBackend)
    result = evaluate(backend, registry, original, plan=plan)
    assert not result.ok
    assert "plan does not match request semantics" in result.diagnostics["exception"]
    assert backend.mock_calls == []


@pytest.mark.parametrize("metadata_change", [False, True])
def test_matching_precompiled_plan_retains_results_and_metadata_independence(
    metadata_change: bool,
) -> None:
    original = request()
    registry = NodeRegistry(REGISTRY)
    plan = EvaluationPlanCompiler.compile(registry, original)
    changed = replace(original, metadata={"note": "display only"}) if metadata_change else original
    backend = MockBackend()
    backend.open(MODEL)
    try:
        direct = evaluate(backend, registry, changed)
        cached_plan = evaluate(backend, registry, changed, plan=plan)
    finally:
        backend.close()
    assert direct.ok and cached_plan.ok
    assert direct.values == cached_plan.values == {"stream.input.temperature:stream=FEED": 100.0}
    assert direct.units == cached_plan.units
    assert direct.violations == cached_plan.violations == []
    assert direct.diagnostics["constraints"] == cached_plan.diagnostics["constraints"]
    assert plan.physical_identity == original.physical_identity()
