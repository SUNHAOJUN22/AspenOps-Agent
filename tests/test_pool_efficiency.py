from __future__ import annotations

from copy import deepcopy
from typing import Any

import aspenops_nexus.pool as pool_module
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.pool import CasePool


def _request(value: float) -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": "model.bkp",
            "registry_path": "registry.json",
            "backend": "mock",
            "writes": [{"key": "feed", "value": value}],
            "reads": [],
        }
    )


def _payload() -> dict[str, Any]:
    return {
        "ok": True,
        "communication_ok": True,
        "engine_ok": True,
        "converged": True,
        "feasible": True,
        "values": {"product": 1.0},
        "units": {"product": "1"},
        "violations": [],
        "diagnostics": {"nested": {"value": 1}},
        "elapsed_s": 0.01,
        "balance_residuals": {},
        "cache_source": "computed",
        "cache_hit": False,
        "request_hash": "",
        "worker_id": 0,
    }


def test_key_requests_normalizes_runtime_identity_once() -> None:
    pool = object.__new__(CasePool)
    runtime_calls = 0
    key_calls = 0
    runtime_identity = {"backend": "mock", "build": {"version": "test"}}

    def runtime() -> dict[str, Any]:
        nonlocal runtime_calls
        runtime_calls += 1
        return runtime_identity

    def key(request: EvaluationRequest, identity: dict[str, Any]) -> str:
        nonlocal key_calls
        key_calls += 1
        assert identity is runtime_identity
        return str(request.writes[0].value)

    pool._runtime_cache_identity = runtime  # type: ignore[method-assign]
    pool._cache_key_with_runtime = key  # type: ignore[method-assign]
    first = _request(1.0)
    second = _request(2.0)

    keyed = pool._key_requests([first, first, second])

    assert runtime_calls == 1
    assert key_calls == 2
    assert [item[0] for item in keyed] == ["1.0", "1.0", "2.0"]


def test_single_cached_result_avoids_redundant_deepcopy(monkeypatch: Any) -> None:
    payload = _payload()

    class Cache:
        def get(self, key: str) -> dict[str, Any]:
            assert key == "same"
            return deepcopy(payload)

    pool = object.__new__(CasePool)
    pool._handles = [object()]  # type: ignore[list-item]
    pool.cache = Cache()  # type: ignore[assignment]
    pool.cache_key = lambda request: "same"  # type: ignore[method-assign]

    def unexpected_deepcopy(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("single cached result must not be copied before parsing")

    monkeypatch.setattr(pool_module, "deepcopy", unexpected_deepcopy)
    result = pool._evaluate_singleflight(_request(1.0), None)

    assert result.cache_source == "persistent_cache"
    assert result.cache_hit
    assert result.request_hash == "same"
    assert payload["diagnostics"]["nested"]["value"] == 1


def test_duplicate_cached_results_are_parsed_once_and_isolated(monkeypatch: Any) -> None:
    payload = _payload()

    class Cache:
        def get_many(self, keys: list[str]) -> dict[str, dict[str, Any]]:
            assert keys == ["same", "same", "same"]
            return {"same": deepcopy(payload)}

    pool = object.__new__(CasePool)
    pool._handles = [object()]  # type: ignore[list-item]
    pool.cache = Cache()  # type: ignore[assignment]
    pool._key_requests = lambda requests: [  # type: ignore[method-assign]
        ("same", request) for request in requests
    ]

    calls = 0
    original = EvaluationResult.from_dict.__func__

    def counting_from_dict(cls: type[EvaluationResult], data: dict[str, Any]) -> EvaluationResult:
        nonlocal calls
        calls += 1
        return original(cls, data)

    monkeypatch.setattr(EvaluationResult, "from_dict", classmethod(counting_from_dict))
    original_replace = pool_module.replace

    def guarded_replace(value: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(value, EvaluationResult):
            raise AssertionError("cached-only fast path must not shallow-copy results")
        return original_replace(value, *args, **kwargs)

    monkeypatch.setattr(pool_module, "replace", guarded_replace)
    results = pool._evaluate_many_locked(
        [_request(1.0), _request(1.0), _request(1.0)],
        cancel_check=None,
    )

    assert calls == 1
    assert len(results) == 3
    assert len({id(result) for result in results}) == 3
    assert all(result.cache_source == "persistent_cache" for result in results)
    assert all(result.cache_hit for result in results)
    results[0].diagnostics["nested"]["value"] = 99
    assert results[1].diagnostics["nested"]["value"] == 1
    assert payload["diagnostics"]["nested"]["value"] == 1
