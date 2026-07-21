from __future__ import annotations

import shutil
from pathlib import Path

from aspenops_nexus.evaluation_plan import EvaluationPlanCompiler
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.pool import CasePool
from aspenops_nexus.registry import NodeRegistry

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def request(
    *,
    model_path: Path = MODEL,
    registry_path: Path = REGISTRY,
    timeout_s: float = 10.0,
    metadata: dict[str, object] | None = None,
    constraint_limit: float = 0.5,
) -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(model_path),
            "registry_path": str(registry_path),
            "backend": "mock",
            "timeout_s": timeout_s,
            "metadata": metadata or {},
            "writes": [],
            "reads": [
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "unit": "fraction",
                }
            ],
            "constraints": [
                {
                    "name": "purity",
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": ">=",
                    "value": constraint_limit,
                    "unit": "fraction",
                }
            ],
        }
    )


def test_compiler_deduplicates_reads_and_is_deterministic() -> None:
    registry = NodeRegistry(REGISTRY)
    first = EvaluationPlanCompiler.compile(registry, request())
    second = EvaluationPlanCompiler.compile(registry, request())
    assert first == second
    assert first.estimated_io.declared_reads == 2
    assert first.estimated_io.unique_read_nodes == 1
    assert first.estimated_io.avoided_duplicate_reads == 1
    assert len(first.unique_reads) == 1


def test_physical_identity_ignores_locations_timeout_and_metadata(tmp_path: Path) -> None:
    copied_model = tmp_path / "renamed-model.json"
    copied_registry = tmp_path / "renamed-registry.json"
    shutil.copy2(MODEL, copied_model)
    shutil.copy2(REGISTRY, copied_registry)
    baseline = request(metadata={"point_index": 1}, timeout_s=10.0)
    relocated = request(
        model_path=copied_model,
        registry_path=copied_registry,
        metadata={"point_index": 999, "label": "relocated"},
        timeout_s=999.0,
    )
    assert baseline.physical_identity() == relocated.physical_identity()


def test_verification_semantics_change_physical_identity() -> None:
    assert (
        request(constraint_limit=0.5).physical_identity()
        != request(constraint_limit=0.9).physical_identity()
    )


def test_same_content_different_paths_share_cache_key(tmp_path: Path) -> None:
    copied_model = tmp_path / "renamed-model.json"
    copied_registry = tmp_path / "renamed-registry.json"
    shutil.copy2(MODEL, copied_model)
    shutil.copy2(REGISTRY, copied_registry)
    cache_path = tmp_path / "cache.sqlite3"
    with CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=cache_path,
    ) as first_pool:
        first_key = first_pool.cache_key(request())
    with CasePool(
        backend_name="mock",
        model_path=copied_model,
        registry_path=copied_registry,
        workers=1,
        visible=False,
        cache_path=cache_path,
    ) as second_pool:
        second_key = second_pool.cache_key(
            request(model_path=copied_model, registry_path=copied_registry)
        )
    assert first_key == second_key


def test_cache_source_distinguishes_dedup_and_persistent_hits(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite3"
    evaluation = request()
    with CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=cache_path,
    ) as pool:
        computed, deduplicated = pool.evaluate_many([evaluation, evaluation])
        persistent = pool.evaluate_many([evaluation])[0]
    assert computed.cache_source == "computed"
    assert computed.cache_hit is False
    assert deduplicated.cache_source == "same_batch_dedup"
    assert deduplicated.cache_hit is True
    assert persistent.cache_source == "persistent_cache"
    assert persistent.cache_hit is True
