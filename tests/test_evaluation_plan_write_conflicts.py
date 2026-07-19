from __future__ import annotations

from pathlib import Path

import pytest

from aspenops_nexus.batch import dry_run_document
from aspenops_nexus.config import Settings
from aspenops_nexus.evaluation_plan import EvaluationPlanCompiler
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.registry import NodeRegistry

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def write(stream: str, value: float) -> dict[str, object]:
    return {
        "key": "stream.input.temperature",
        "identifiers": {"stream": stream},
        "value": value,
        "unit": "C",
    }


def request(writes: list[dict[str, object]]) -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": writes,
            "reads": [],
        }
    )


def test_compiler_rejects_duplicate_semantic_write_target() -> None:
    registry = NodeRegistry(REGISTRY)
    with pytest.raises(
        ValueError,
        match=r"Duplicate write target: stream\.input\.temperature:stream=FEED",
    ):
        EvaluationPlanCompiler.compile(
            registry,
            request([write("FEED", 70.0), write("FEED", 80.0)]),
        )


def test_compiler_allows_same_semantic_key_for_distinct_identifiers() -> None:
    plan = EvaluationPlanCompiler.compile(
        NodeRegistry(REGISTRY),
        request([write("FEED-A", 70.0), write("FEED-B", 80.0)]),
    )
    assert plan.estimated_io.declared_writes == 2
    assert plan.estimated_io.unique_write_nodes == 2


def test_dry_run_rejects_base_and_point_write_conflict(tmp_path: Path) -> None:
    document = {
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
        "backend": "mock",
        "base_writes": [write("FEED", 70.0)],
        "points": [{"writes": [write("FEED", 80.0)]}],
        "reads": [],
    }
    with pytest.raises(ValueError, match="Duplicate write target"):
        dry_run_document(document, Settings(state_dir=tmp_path))
