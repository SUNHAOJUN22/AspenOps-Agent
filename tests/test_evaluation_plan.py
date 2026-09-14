from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from aspenops_nexus import RUNTIME_SCHEMA, __version__
from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.evaluation_plan import EvaluationPlanCompiler
from aspenops_nexus.hashing import canonical_hash
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.pool import CasePool
from aspenops_nexus.registry import NodeRegistry, RegistryError

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


@pytest.fixture
def identity_case(tmp_path: Path) -> tuple[Path, Path]:
    model = tmp_path / "model.json"
    model.write_text(json.dumps({"inputs": {"first_pressure": 2.0, "second_pressure": 20.0}}))
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "nodes": {
                    "pressure": {
                        "access": "readwrite",
                        "backend": "mock",
                        "unit": "bar",
                        "identifiers": ["block"],
                        "locator": {"mock_key": "first_pressure"},
                    },
                    "pressure:block=R1": {
                        "access": "readwrite",
                        "backend": "mock",
                        "unit": "bar",
                        "locator": {"mock_key": "second_pressure"},
                    },
                }
            }
        )
    )
    return model, registry


def identity_request(
    case: tuple[Path, Path],
    first: str = "reads",
    second: str = "constraints",
    *,
    reverse: bool = False,
) -> EvaluationRequest:
    nodes = [("pressure", {"block": "R1"}), ("pressure:block=R1", {})]
    if reverse:
        nodes.reverse()
    data = {
        "backend": "mock",
        "model_path": str(case[0]),
        "registry_path": str(case[1]),
        "writes": [],
        "reads": [],
        "constraints": [],
        "balances": [],
    }
    for location, (key, identifiers) in zip((first, second), nodes, strict=True):
        item = {"key": key, "identifiers": identifiers, "unit": "bar"}
        if location == "writes":
            item["value"] = 4.0
        elif location == "constraints":
            item.update(operator="<=", value=10.0)
        elif location == "balances":
            item["coefficient"] = 1.0
            data[location].append({"name": f"balance_{len(data[location])}", "terms": [item]})
            continue
        data[location].append(item)
    return EvaluationRequest.from_dict(data)


@pytest.mark.parametrize(
    "first,second",
    [
        ("reads", "constraints"),
        ("reads", "balances"),
        ("constraints", "constraints"),
        ("constraints", "balances"),
        ("balances", "balances"),
        ("writes", "reads"),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_distinct_semantic_nodes_cannot_share_a_display_identity(
    identity_case: tuple[Path, Path], first: str, second: str, reverse: bool
) -> None:
    evaluation = identity_request(identity_case, first, second, reverse=reverse)
    with pytest.raises(RegistryError, match="Ambiguous semantic identity"):
        EvaluationPlanCompiler.compile(NodeRegistry(identity_case[1]), evaluation)


def test_unknown_colliding_constraint_is_not_resolved_from_another_read(
    identity_case: tuple[Path, Path],
) -> None:
    path = identity_case[1]
    document = json.loads(path.read_text())
    del document["nodes"]["pressure:block=R1"]
    path.write_text(json.dumps(document))
    with pytest.raises(RegistryError):
        EvaluationPlanCompiler.compile(NodeRegistry(path), identity_request(identity_case))


def test_identifier_punctuation_cannot_alias_a_valid_identifier_mapping(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "nodes": {
                    "flow": {
                        "backend": "mock",
                        "access": "read",
                        "unit": "kg/s",
                        "identifiers": ["a", "b"],
                        "locator": {"mock_key": "flow"},
                    }
                }
            }
        )
    )
    evaluation = EvaluationRequest.from_dict(
        {
            "backend": "mock",
            "model_path": str(MODEL),
            "registry_path": str(path),
            "writes": [],
            "reads": [{"key": "flow", "identifiers": {"a": "1", "b": "2"}}],
            "constraints": [{"key": "flow", "identifiers": {"a": "1,b=2"}, "value": 1}],
        }
    )
    with pytest.raises(RegistryError):
        EvaluationPlanCompiler.compile(NodeRegistry(path), evaluation)


def test_ambiguous_plan_is_rejected_before_backend_state_changes(
    identity_case: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    evaluation = identity_request(identity_case)
    backend = MockBackend()
    backend.open(identity_case[0])
    calls: list[str] = []
    for method in ("reinitialize", "bulk_write", "run", "bulk_read"):
        original = getattr(backend, method)

        def record(*args: object, _name: str = method, _original=original):
            calls.append(_name)
            return _original(*args)

        monkeypatch.setattr(backend, method, record)
    try:
        result = evaluate(backend, NodeRegistry(identity_case[1]), evaluation)
    finally:
        backend.close()
    assert not result.ok and not result.feasible
    assert not calls
    assert "Ambiguous semantic identity" in json.dumps(result.to_dict())


def legacy_pool_key(pool: CasePool, evaluation: EvaluationRequest) -> str:
    identity = {
        "schema": RUNTIME_SCHEMA,
        "runtime_version": __version__,
        "backend": pool.backend_name,
        "runtime_identity": pool._runtime_cache_identity(),
        "model_sha256": pool.model_sha256,
        "registry_sha256": pool._registry_digest(),
        "request": evaluation.physical_identity(),
    }
    if any(spec.operator in {"<", ">"} for spec in evaluation.constraints):
        identity["strict_constraint_semantics"] = "open-boundary-v1"
    return canonical_hash(identity)


@pytest.mark.parametrize("batch_size", [1, 2])
def test_legacy_cached_success_cannot_bypass_identity_validation(
    identity_case: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    batch_size: int,
) -> None:
    pool = CasePool(
        backend_name="mock",
        model_path=identity_case[0],
        registry_path=identity_case[1],
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )
    # No processes or simulator execution: exercise only persisted-result admission.
    monkeypatch.setattr(pool, "start", lambda: None)
    evaluation = identity_request(identity_case)
    key = legacy_pool_key(pool, evaluation)
    cached = EvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values={},
        units={},
        violations=[],
        diagnostics={},
        elapsed_s=0.0,
    )
    try:
        pool.cache.put(key, cached.to_dict())
        with pytest.raises(RegistryError, match="Ambiguous semantic identity"):
            pool.evaluate_many([evaluation] * batch_size)
        # Rejection must not delete historical evidence.
        assert pool.cache.get(key) is not None
    finally:
        pool.close()


@pytest.mark.parametrize("literal", [False, True])
def test_unambiguous_keys_and_read_deduplication_remain_compatible(
    identity_case: tuple[Path, Path], tmp_path: Path, literal: bool
) -> None:
    key, identifiers = ("pressure:block=R1", {}) if literal else ("pressure", {"block": "R1"})
    evaluation = EvaluationRequest.from_dict(
        {
            "backend": "mock",
            "model_path": str(identity_case[0]),
            "registry_path": str(identity_case[1]),
            "writes": [],
            "reads": [{"key": key, "identifiers": identifiers}],
            "constraints": [{"key": key, "identifiers": identifiers, "value": 0, "operator": ">="}],
        }
    )
    plan = EvaluationPlanCompiler.compile(NodeRegistry(identity_case[1]), evaluation)
    assert plan.estimated_io.unique_read_nodes == 1
    assert plan.estimated_io.avoided_duplicate_reads == 1
    assert plan.constraints[0].node.key == key
    pool = CasePool(
        backend_name="mock",
        model_path=identity_case[0],
        registry_path=identity_case[1],
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )
    try:
        assert pool.cache_key(evaluation) == legacy_pool_key(pool, evaluation)
    finally:
        pool.close()
