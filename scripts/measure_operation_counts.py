from __future__ import annotations

import argparse
import cProfile
import json
import os
import platform
import pstats
import tempfile
import tracemalloc
from pathlib import Path
from typing import Any

import psutil

import aspenops_nexus.cache as cache_module
import aspenops_nexus.optimizer as optimizer
import aspenops_nexus.pool as pool_module
from aspenops_nexus.cache import ResultCache
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.optimizer import ParetoPoint, pareto_front
from aspenops_nexus.pool import CasePool
from aspenops_nexus.worker import WorkerHandle

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


class AliveProcess:
    def is_alive(self) -> bool:
        return True


class UnusedConnection:
    pass


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
        }
    )


def result(handle: WorkerHandle) -> EvaluationResult:
    return EvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values={"stream.output.purity:stream=PRODUCT": 0.99},
        units={"stream.output.purity:stream=PRODUCT": "fraction"},
        violations=[],
        diagnostics={"nested": {"value": 1}},
        elapsed_s=0.0,
        worker_id=handle.worker_id,
    )


def pool_counts(directory: Path) -> dict[str, Any]:
    active_pool = CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=directory / "pool-cache.sqlite3",
    )
    active_pool._handles = [
        WorkerHandle(
            worker_id=0,
            process=AliveProcess(),
            connection=UnusedConnection(),  # type: ignore[arg-type]
            staged_model=MODEL,
            runtime={"backend": "mock"},
        )
    ]
    cache_key_calls = 0
    solver_calls = 0
    serialization_calls = 0
    original_cache_key = active_pool.cache_key
    original_evaluate = pool_module.evaluate_on_worker
    original_to_dict = EvaluationResult.to_dict

    def counted_cache_key(active_request: EvaluationRequest) -> str:
        nonlocal cache_key_calls
        cache_key_calls += 1
        return original_cache_key(active_request)

    def fake_evaluate(
        handle: WorkerHandle,
        active_request: EvaluationRequest,
    ) -> EvaluationResult:
        nonlocal solver_calls
        del active_request
        solver_calls += 1
        return result(handle)

    def counted_to_dict(self: EvaluationResult) -> dict[str, Any]:
        nonlocal serialization_calls
        serialization_calls += 1
        return original_to_dict(self)

    active_pool.cache_key = counted_cache_key  # type: ignore[method-assign]
    pool_module.evaluate_on_worker = fake_evaluate
    EvaluationResult.to_dict = counted_to_dict
    try:
        repeated = request()
        results = active_pool.evaluate_many([repeated] * 100)
    finally:
        active_pool.cache_key = original_cache_key  # type: ignore[method-assign]
        pool_module.evaluate_on_worker = original_evaluate
        EvaluationResult.to_dict = original_to_dict

    results[1].diagnostics["nested"]["value"] = 99
    isolated = (
        results[0].diagnostics["nested"]["value"] == 1
        and results[2].diagnostics["nested"]["value"] == 1
    )
    return {
        "points": 100,
        "cache_key_calls": cache_key_calls,
        "solver_calls": solver_calls,
        "result_serializations": serialization_calls,
        "computed_results": sum(item.cache_source == "computed" for item in results),
        "same_batch_dedup_results": sum(
            item.cache_source == "same_batch_dedup" for item in results
        ),
        "deep_result_isolation": isolated,
    }


def cache_counts(directory: Path) -> dict[str, Any]:
    cache = ResultCache(directory / "result-cache.sqlite3")
    payloads = {f"key-{index}": {"index": index} for index in range(1024)}
    cache.put_many(payloads)
    loaded = cache.get_many(list(payloads))
    stats = cache.stats()
    return {
        "requested_keys": len(payloads),
        "loaded_keys": len(loaded),
        "pending_hit_total_after_threshold": cache._pending_hit_total,
        "persistent_hits": stats["hits"],
    }


def memory_cache_counts(directory: Path) -> dict[str, Any]:
    cache = ResultCache(directory / "memory-result-cache.sqlite3")
    cache.put("hot", {"value": {"nested": 1}})
    decode_calls = 0
    connection_calls = 0
    original_loads = cache_module.json.loads
    original_connect = cache._connect

    def counted_loads(value: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal decode_calls
        decode_calls += 1
        return original_loads(value, *args, **kwargs)

    def counted_connect() -> Any:
        nonlocal connection_calls
        connection_calls += 1
        return original_connect()

    cache_module.json.loads = counted_loads
    cache._connect = counted_connect  # type: ignore[method-assign]
    try:
        first = cache.get_many(["hot", "hot"])
        first["hot"]["value"]["nested"] = 99
        second = cache.get("hot")
    finally:
        cache_module.json.loads = original_loads
        cache._connect = original_connect  # type: ignore[method-assign]

    return {
        "requested_hits": 3,
        "json_decode_calls": decode_calls,
        "sqlite_connection_calls": connection_calls,
        "deep_result_isolation": second == {"value": {"nested": 1}},
    }


def pareto_counts() -> dict[str, Any]:
    point = ParetoPoint((1.0,), (1.0, 2.0), 0.0)
    calls = 0
    original = optimizer.dominates

    def counted(left: ParetoPoint, right: ParetoPoint) -> bool:
        nonlocal calls
        calls += 1
        return original(left, right)

    optimizer.dominates = counted
    try:
        front = pareto_front([point] * 1000)
    finally:
        optimizer.dominates = original
    return {
        "input_points": 1000,
        "front_points": len(front),
        "dominance_calls": calls,
    }


def environment() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    return {
        "git_commit": os.getenv("GITHUB_SHA") or os.getenv("ASPENOPS_GIT_COMMIT"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_logical": psutil.cpu_count(logical=True),
        "memory_total_bytes": int(memory.total),
    }


def profile_summary(profile: cProfile.Profile, limit: int = 20) -> dict[str, Any]:
    stats = pstats.Stats(profile)
    rows: list[dict[str, Any]] = []
    for (filename, line, function), values in stats.stats.items():
        primitive_calls, total_calls, total_time, cumulative_time, _ = values
        rows.append(
            {
                "file": Path(filename).name,
                "line": int(line),
                "function": function,
                "primitive_calls": int(primitive_calls),
                "total_calls": int(total_calls),
                "total_time_s": float(total_time),
                "cumulative_time_s": float(cumulative_time),
            }
        )
    rows.sort(key=lambda item: (-item["cumulative_time_s"], -item["total_time_s"]))
    return {
        "total_calls": int(stats.total_calls),
        "primitive_calls": int(stats.prim_calls),
        "total_profiled_time_s": float(stats.total_tt),
        "top_cumulative_functions": rows[:limit],
        "boundary": (
            "cProfile is a diagnostic run with profiler overhead. Operation counts are the hard "
            "performance contracts and are interpreted separately from profiled wall time."
        ),
    }


def run_probe() -> dict[str, Any]:
    process = psutil.Process()
    rss_before = int(process.memory_info().rss)
    profiler = cProfile.Profile()
    tracemalloc.start(10)
    profiler.enable()
    with tempfile.TemporaryDirectory(prefix="aspenops-operation-counts-") as temporary:
        directory = Path(temporary)
        pool = pool_counts(directory)
        cache = cache_counts(directory)
        memory_cache = memory_cache_counts(directory)
        pareto = pareto_counts()
    profiler.disable()
    traced_current, traced_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_after = int(process.memory_info().rss)
    return {
        "schema": "aspenops.operation-counts/v2",
        "kind": "portable-deterministic-performance-contracts",
        "boundary": (
            "These are deterministic Python orchestration operation counts. They do not "
            "measure licensed Aspen Plus/HYSYS solve performance."
        ),
        "environment": environment(),
        "pool": pool,
        "cache": cache,
        "memory_cache": memory_cache,
        "pareto": pareto,
        "memory": {
            "rss_before_bytes": rss_before,
            "rss_after_bytes": rss_after,
            "rss_delta_bytes": rss_after - rss_before,
            "traced_current_bytes": int(traced_current),
            "traced_peak_bytes": int(traced_peak),
            "tracemalloc_frames": 10,
        },
        "profile": profile_summary(profiler),
        "expected": {
            "pool.cache_key_calls": 1,
            "pool.solver_calls": 1,
            "pool.result_serializations": 1,
            "pool.same_batch_dedup_results": 99,
            "pool.deep_result_isolation": True,
            "cache.pending_hit_total_after_threshold": 0,
            "memory_cache.json_decode_calls": 0,
            "memory_cache.sqlite_connection_calls": 0,
            "memory_cache.deep_result_isolation": True,
            "pareto.dominance_calls": 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(run_probe(), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
