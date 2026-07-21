from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.pool import CasePool
from aspenops_nexus.worker import WorkerHandle

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "unit": "fraction",
                }
            ],
            "timeout_s": 10,
        }
    )


def test_concurrent_identical_single_points_use_one_solver_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    calls_lock = threading.Lock()
    start_gate = threading.Barrier(2)

    def fake_evaluate(
        handle: WorkerHandle,
        evaluation_request: EvaluationRequest,
    ) -> EvaluationResult:
        nonlocal calls
        del evaluation_request
        with calls_lock:
            calls += 1
        time.sleep(0.2)
        return EvaluationResult(
            ok=True,
            communication_ok=True,
            engine_ok=True,
            converged=True,
            feasible=True,
            values={"stream.output.purity:stream=PRODUCT": 0.99},
            units={"stream.output.purity:stream=PRODUCT": "fraction"},
            violations=[],
            diagnostics={"fake_solver": True},
            elapsed_s=0.2,
            worker_id=handle.worker_id,
        )

    monkeypatch.setattr("aspenops_nexus.pool.evaluate_on_worker", fake_evaluate)
    with CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    ) as pool:

        def run() -> EvaluationResult:
            start_gate.wait()
            return pool.evaluate_many([request()])[0]

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(run)
            second_future = executor.submit(run)
            results = [first_future.result(), second_future.result()]

    assert calls == 1
    assert sorted(result.cache_source for result in results) == [
        "computed",
        "inflight_singleflight",
    ]
    assert sum(result.cache_hit for result in results) == 1
    assert results[0].request_hash == results[1].request_hash
