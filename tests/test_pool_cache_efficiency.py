from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.pool import CasePool

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def request(temperature: float, *, reset_mode: str = "reinitialize") -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "reset_mode": reset_mode,
            "writes": [
                {
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "value": temperature,
                    "unit": "C",
                }
            ],
            "reads": [
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "unit": "fraction",
                }
            ],
        }
    )


def result(
    *,
    ok: bool,
    communication_ok: bool,
    engine_ok: bool,
    worker_tainted: bool = False,
) -> EvaluationResult:
    return EvaluationResult(
        ok=ok,
        communication_ok=communication_ok,
        engine_ok=engine_ok,
        converged=ok,
        feasible=ok,
        values={},
        units={},
        violations=[] if ok else ["simulator_not_converged:not_converged"],
        diagnostics={"worker_tainted": worker_tainted},
        elapsed_s=0.0,
    )


def test_batch_uses_one_cache_read_and_write_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = [request(70.0), request(80.0), request(70.0)]
    with CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    ) as pool:
        get_calls: list[list[str]] = []
        put_calls: list[dict[str, dict[str, Any]]] = []
        original_get_many = pool.cache.get_many
        original_put_many = pool.cache.put_many

        def get_many(keys: list[str]) -> dict[str, dict[str, Any]]:
            get_calls.append(list(keys))
            return original_get_many(keys)

        def put_many(payloads: dict[str, dict[str, Any]]) -> None:
            put_calls.append(dict(payloads))
            original_put_many(payloads)

        monkeypatch.setattr(pool.cache, "get_many", get_many)
        monkeypatch.setattr(pool.cache, "put_many", put_many)

        cold = pool.evaluate_many(requests)
        assert len(get_calls) == 1
        assert len(get_calls[0]) == 3
        assert len(put_calls) == 1
        assert len(put_calls[0]) == 2
        assert [item.cache_source for item in cold] == [
            "computed",
            "computed",
            "same_batch_dedup",
        ]

        get_calls.clear()
        put_calls.clear()
        warm = pool.evaluate_many(requests)
        assert len(get_calls) == 1
        assert len(get_calls[0]) == 3
        assert put_calls == []
        assert {item.cache_source for item in warm} == {"persistent_cache"}


def test_all_cached_batch_skips_dispatch_thread_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = [request(70.0), request(80.0)]
    with CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    ) as pool:
        assert all(item.ok for item in pool.evaluate_many(requests))

        def unexpected_thread(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            pytest.fail("dispatch thread created for an all-cache-hit batch")

        monkeypatch.setattr("aspenops_nexus.pool.threading.Thread", unexpected_thread)
        cached = pool.evaluate_many(requests)
    assert all(item.cache_source == "persistent_cache" for item in cached)


def test_failure_cache_excludes_transient_and_tainted_results(tmp_path: Path) -> None:
    pool = CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
        cache_failures=True,
    )
    reinitialized = request(70.0)
    warm_start = request(70.0, reset_mode="warm_start")

    assert pool._cacheable(
        reinitialized,
        result(ok=True, communication_ok=True, engine_ok=True),
    )
    assert pool._cacheable(
        reinitialized,
        result(ok=False, communication_ok=True, engine_ok=True),
    )
    assert not pool._cacheable(
        reinitialized,
        result(ok=False, communication_ok=False, engine_ok=False),
    )
    assert not pool._cacheable(
        reinitialized,
        result(
            ok=False,
            communication_ok=True,
            engine_ok=True,
            worker_tainted=True,
        ),
    )
    assert not pool._cacheable(
        warm_start,
        result(ok=True, communication_ok=True, engine_ok=True),
    )


def test_concurrent_start_only_creates_one_worker_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=3,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )
    created: list[int] = []

    def new_handle(worker_id: int) -> Any:
        time.sleep(0.01)
        created.append(worker_id)
        return SimpleNamespace(worker_id=worker_id, generation=0)

    monkeypatch.setattr(pool, "_new_handle", new_handle)
    callers = [threading.Thread(target=pool.start) for _ in range(4)]
    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join()

    assert sorted(created) == [0, 1, 2]
    assert len(pool._handles) == 3
    pool._handles.clear()
