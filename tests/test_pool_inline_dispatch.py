from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.pool import CasePool

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def request(temperature: float, *, warm_step: int | None = None) -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "reset_mode": "reinitialize" if warm_step is None else "warm_start",
            "metadata": {"warm_start_session": "inline-trajectory", "warm_start_step": warm_step},
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


def test_single_worker_avoids_thread_churn_and_preserves_live_trajectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    ) as pool:
        worker = pool._handles[0]
        assert worker.process.pid != os.getpid()

        def unexpected_dispatch(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            pytest.fail("single-worker synchronous request created a dispatch thread")

        monkeypatch.setattr("aspenops_nexus.pool.threading.Thread", unexpected_dispatch)
        cold = request(70.0)
        first = pool.evaluate_many([cold])[0]
        continuation = pool.evaluate_many([request(80.0, warm_step=1)])[0]
        assert first.ok and continuation.ok
        assert first.cache_source == continuation.cache_source == "computed"
        assert pool._handles[0] is worker
        assert first.worker_id == continuation.worker_id
        assert (
            first.diagnostics["execution_identity"]
            == continuation.diagnostics["execution_identity"]
        )

        # Reading a cold result from cache still cannot restore live solver state.
        cached = pool.evaluate_many([cold])[0]
        assert cached.cache_source == "persistent_cache"
        lost = pool.evaluate_many([request(90.0, warm_step=2)])[0]
        assert not lost.ok
        assert "warm_start_state_lost" in lost.violations


def test_multiple_active_workers_keep_parallel_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=2,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    ) as pool:
        original = threading.Thread
        dispatch_names: list[str] = []

        def observed_thread(*args: Any, **kwargs: Any) -> threading.Thread:
            dispatch_names.append(kwargs.get("name", ""))
            return original(*args, **kwargs)

        monkeypatch.setattr("aspenops_nexus.pool.threading.Thread", observed_thread)
        results = pool.evaluate_many([request(70.0), request(80.0)])
        assert all(result.ok for result in results)
        assert set(dispatch_names) == {"aspenops-dispatch-0", "aspenops-dispatch-1"}
        assert len(pool._handles) == 2
