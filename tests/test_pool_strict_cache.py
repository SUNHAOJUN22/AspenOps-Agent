from __future__ import annotations

from pathlib import Path

import pytest

from aspenops_nexus import RUNTIME_SCHEMA, __version__
from aspenops_nexus.cache import ResultCache
from aspenops_nexus.hashing import canonical_hash
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.pool import CasePool

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


@pytest.mark.parametrize("operator", [None, "<", "<=", ">", ">=", "=="])
@pytest.mark.parametrize("tolerance", [0.0, 0.125])
def test_strict_constraint_cache_identity_does_not_reuse_legacy_results(
    tmp_path: Path, operator: str | None, tolerance: float
) -> None:
    constraints = []
    if operator is not None:
        constraints.append(
            {
                "name": "boundary",
                "key": "stream.output.purity",
                "identifiers": {"stream": "PRODUCT"},
                "operator": operator,
                "value": 1.0,
                "tolerance": tolerance,
                "unit": "fraction",
            }
        )
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "constraints": constraints,
        }
    )
    cache_path = tmp_path / "cache.sqlite3"
    pool = CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=cache_path,
    )
    # Reconstruct the exact previous key without starting any simulator worker.
    legacy_key = canonical_hash(
        {
            "schema": RUNTIME_SCHEMA,
            "runtime_version": __version__,
            "backend": pool.backend_name,
            "runtime_identity": pool._runtime_cache_identity(),
            "model_sha256": pool.model_sha256,
            "registry_sha256": pool._registry_digest(),
            "request": request.physical_identity(),
        }
    )
    old_payload = {"ok": True, "origin": "synthetic-legacy-cache"}
    pool.cache.put(legacy_key, old_payload)
    key = pool.cache_key(request)
    strict = operator in {"<", ">"}
    assert (key != legacy_key) is strict
    assert pool._key_requests([request, request]) == [(key, request), (key, request)]
    if strict:
        assert pool.cache.get(key) is None
        assert pool.cache.get_many([key]) == {}
        pool.cache.put(key, {"ok": False, "origin": "synthetic-current-cache"})
    else:
        assert pool.cache.get(key) == old_payload
    pool.close()
    reopened = ResultCache(cache_path)
    try:
        assert reopened.get(legacy_key) == old_payload
        expected = {"ok": False, "origin": "synthetic-current-cache"} if strict else old_payload
        assert reopened.get(key) == expected
    finally:
        reopened.close()
