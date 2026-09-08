from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.evaluation_plan import EvaluationPlanCompiler
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.registry import NodeRegistry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"


def _request() -> EvaluationRequest:
    node = {
        "key": "stream.output.purity",
        "identifiers": {"stream": "PRODUCT"},
        "unit": "fraction",
    }
    constraints = [
        {
            **node,
            "name": f"purity-{index}",
            "operator": ">=",
            "value": 0.5,
        }
        for index in range(3)
    ]
    balance_terms = [{**node, "coefficient": float(index + 1)} for index in range(4)]
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [node],
            "constraints": constraints,
            "balances": [
                {
                    "name": "purity-reuse",
                    "terms": balance_terms,
                    "expected": 0.0,
                }
            ],
        }
    )


def test_duplicate_read_references_resolve_once(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = NodeRegistry(REGISTRY)
    calls: list[tuple[str, dict[str, str]]] = []
    original = registry.resolve

    def counted(key: str, identifiers: dict[str, str]) -> Any:
        calls.append((key, dict(identifiers)))
        return original(key, identifiers)

    monkeypatch.setattr(registry, "resolve", counted)
    plan = EvaluationPlanCompiler.compile(registry, _request())

    assert calls == [("stream.output.purity", {"stream": "PRODUCT"})]
    assert plan.estimated_io.declared_reads == 8
    assert plan.estimated_io.unique_read_nodes == 1
    assert plan.estimated_io.avoided_duplicate_reads == 7
    assert len(plan.output_bindings) == 1
    assert len(plan.constraints) == 3
    assert len(plan.balances) == 1
    assert len(plan.balances[0].terms) == 4


def test_duplicate_binding_semantics_remain_deterministic() -> None:
    registry = NodeRegistry(REGISTRY)
    first = EvaluationPlanCompiler.compile(registry, _request())
    second = EvaluationPlanCompiler.compile(registry, _request())

    assert first == second
    identity = "stream.output.purity:stream=PRODUCT"
    assert first.output_bindings[0].identity == identity
    assert all(item.identity == identity for item in first.constraints)
    assert all(item.identity == identity for item in first.balances[0].terms)
