from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import aspenops_nexus.pool as pool_module
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.pool import CasePool
from aspenops_nexus.worker import WorkerHandle


class AliveProcess:
    def is_alive(self) -> bool:
        return True


class UnusedConnection:
    pass


class EmptyCache:
    def get_many(self, keys: list[str]) -> dict[str, dict[str, Any]]:
        del keys
        return {}

    def put_many(self, payloads: dict[str, dict[str, Any]]) -> None:
        if payloads:
            raise AssertionError("benchmark results must not be cached")


REQUEST = EvaluationRequest.from_dict(
    {
        "model_path": "model.bkp",
        "registry_path": "registry.json",
        "backend": "mock",
        "writes": [],
        "reads": [],
    }
)


def result(handle: WorkerHandle) -> EvaluationResult:
    return EvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values={"value": 1.0},
        units={"value": "1"},
        violations=[],
        diagnostics={"nested": {"value": 1}},
        elapsed_s=0.0,
        worker_id=handle.worker_id,
    )


def make_pool() -> CasePool:
    active = object.__new__(CasePool)
    active._handles = [
        WorkerHandle(
            worker_id=0,
            process=AliveProcess(),
            connection=UnusedConnection(),  # type: ignore[arg-type]
            staged_model=Path("model.bkp"),
            runtime={"backend": "mock"},
        )
    ]
    active.cache = EmptyCache()  # type: ignore[assignment]
    active.cache_failures = False
    active._key_requests = lambda requests: [  # type: ignore[method-assign]
        (f"key-{index}", request) for index, request in enumerate(requests)
    ]
    active._recycle_reason = lambda handle: None  # type: ignore[method-assign]
    active._result_recycle_reason = (  # type: ignore[method-assign]
        lambda handle, active_result: None
    )
    active._cacheable = lambda request, active_result: False  # type: ignore[method-assign]
    return active


def measure(function: Callable[[], int], repeats: int) -> tuple[float, int]:
    samples: list[float] = []
    reference: int | None = None
    for _ in range(2):
        observed = function()
        reference = observed if reference is None else reference
        if observed != reference:
            raise AssertionError("benchmark warm-up checksum changed")
    for _ in range(repeats):
        gc.collect()
        started = time.perf_counter()
        observed = function()
        samples.append(time.perf_counter() - started)
        if observed != reference:
            raise AssertionError("benchmark checksum changed")
    assert reference is not None
    return statistics.median(samples), reference


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    original_evaluate = pool_module.evaluate_on_worker
    pool_module.evaluate_on_worker = lambda handle, request: result(handle)
    try:
        single_pool = make_pool()
        batch_pool = make_pool()
        single_iterations = 1200
        batch_points = 12000
        batch_requests = [REQUEST] * batch_points

        def single_probe() -> int:
            checksum = 0
            for _ in range(single_iterations):
                values = single_pool._evaluate_many_locked([REQUEST], cancel_check=None)
                checksum += len(values)
            return checksum

        def batch_probe() -> int:
            values = batch_pool._evaluate_many_locked(batch_requests, cancel_check=None)
            return len(values) + sum(item.request_hash is not None for item in values)

        single_seconds, single_checksum = measure(single_probe, 7)
        batch_seconds, batch_checksum = measure(batch_probe, 7)
    finally:
        pool_module.evaluate_on_worker = original_evaluate

    payload = {
        "single_seconds": single_seconds,
        "batch_seconds": batch_seconds,
        "single_iterations": single_iterations,
        "batch_points": batch_points,
        "single_checksum": single_checksum,
        "batch_checksum": batch_checksum,
    }
    Path(args.output).write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
