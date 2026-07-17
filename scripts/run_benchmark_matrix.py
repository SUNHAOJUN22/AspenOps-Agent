from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil

from aspenops_nexus.models import EvaluationRequest, VariableRead, VariableWrite
from aspenops_nexus.pool import CasePool

try:
    from aspenops_nexus.pool_manager import PoolManager
except ImportError:
    PoolManager = None  # type: ignore[misc,assignment]


@dataclass(frozen=True, slots=True)
class Measurement:
    scenario: str
    points: int
    workers: int
    duplicate_ratio: float
    cache_mode: str
    elapsed_s: float
    throughput_points_s: float
    p50_point_s: float
    p95_point_s: float
    p99_point_s: float
    rss_before: int
    rss_after: int
    rss_delta: int
    ok_points: int
    failed_points: int
    cache_sources: dict[str, int]


def percentile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * probability)))
    return ordered[index]


def build_requests(
    *,
    model_path: Path,
    registry_path: Path,
    points: int,
    duplicate_ratio: float = 0.0,
    timeout_s: float = 30.0,
    failing: bool = False,
) -> list[EvaluationRequest]:
    unique_count = max(1, round(points * (1.0 - duplicate_ratio)))
    unique: list[EvaluationRequest] = []
    for index in range(unique_count):
        temperature = 200.0 if failing else 50.0 + (index % 60)
        unique.append(
            EvaluationRequest(
                model_path=str(model_path),
                registry_path=str(registry_path),
                backend="mock",
                writes=(
                    VariableWrite(
                        "stream.input.temperature",
                        {"stream": "FEED"},
                        temperature,
                        "C",
                    ),
                    VariableWrite(
                        "block.input.reflux_ratio",
                        {"block": "COL1"},
                        1.2 + 0.03 * (index % 30),
                        "1",
                    ),
                ),
                reads=(
                    VariableRead(
                        "stream.output.purity",
                        {"stream": "PRODUCT"},
                        "fraction",
                    ),
                    VariableRead(
                        "block.output.reboiler_duty",
                        {"block": "COL1"},
                        "kW",
                    ),
                ),
                timeout_s=timeout_s,
            )
        )
    return [unique[index % unique_count] for index in range(points)]


def cache_source(result: Any) -> str:
    source = getattr(result, "cache_source", None)
    if source:
        return str(source)
    return "persistent_cache" if bool(getattr(result, "cache_hit", False)) else "computed"


def measure_pool(
    *,
    scenario: str,
    model_path: Path,
    registry_path: Path,
    points: int,
    workers: int,
    duplicate_ratio: float = 0.0,
    warm_cache: bool = False,
    failing: bool = False,
) -> Measurement:
    state_dir = Path(tempfile.mkdtemp(prefix="aspenops-benchmark-"))
    cache_path = state_dir / "cache.sqlite3"
    requests = build_requests(
        model_path=model_path,
        registry_path=registry_path,
        points=points,
        duplicate_ratio=duplicate_ratio,
        failing=failing,
    )
    process = psutil.Process(os.getpid())
    rss_before = int(process.memory_info().rss)
    with CasePool(
        backend_name="mock",
        model_path=model_path,
        registry_path=registry_path,
        workers=workers,
        visible=False,
        cache_path=cache_path,
    ) as pool:
        if warm_cache:
            pool.evaluate_many(requests)
        started = time.perf_counter()
        results = pool.evaluate_many(requests)
        elapsed = time.perf_counter() - started
    rss_after = int(process.memory_info().rss)
    latencies = [float(item.elapsed_s) for item in results]
    sources: dict[str, int] = {}
    for item in results:
        source = cache_source(item)
        sources[source] = sources.get(source, 0) + 1
    return Measurement(
        scenario=scenario,
        points=points,
        workers=workers,
        duplicate_ratio=duplicate_ratio,
        cache_mode="warm" if warm_cache else "cold",
        elapsed_s=elapsed,
        throughput_points_s=points / max(elapsed, 1e-12),
        p50_point_s=statistics.median(latencies) if latencies else 0.0,
        p95_point_s=percentile(latencies, 0.95),
        p99_point_s=percentile(latencies, 0.99),
        rss_before=rss_before,
        rss_after=rss_after,
        rss_delta=rss_after - rss_before,
        ok_points=sum(1 for item in results if item.ok),
        failed_points=sum(1 for item in results if not item.ok),
        cache_sources=sources,
    )


def sequential_job_measurement(
    *,
    model_path: Path,
    registry_path: Path,
    workers: int,
) -> dict[str, Any]:
    if PoolManager is None:
        return {
            "scenario": "ten_sequential_jobs",
            "available": False,
            "reason": "PoolManager is unavailable in this revision",
        }
    state_dir = Path(tempfile.mkdtemp(prefix="aspenops-sequential-"))
    requests = build_requests(
        model_path=model_path,
        registry_path=registry_path,
        points=10,
    )
    started = time.perf_counter()
    with PoolManager(
        cache_path=state_dir / "cache.sqlite3",
        license_slots=workers,
        max_resident_cases=1,
        idle_timeout_s=3600,
    ) as manager:
        for _ in range(10):
            with manager.acquire(
                backend_name="mock",
                model_path=model_path,
                registry_path=registry_path,
                workers=workers,
                visible=False,
            ) as pool:
                pool.evaluate_many(requests)
        stats = manager.stats()
    return {
        "scenario": "ten_sequential_jobs",
        "available": True,
        "elapsed_s": time.perf_counter() - started,
        "pool_stats": stats,
    }


def run_matrix(repo_root: Path, *, smoke: bool) -> dict[str, Any]:
    model_path = repo_root / "src/aspenops_nexus/data/mock-case.json"
    registry_path = repo_root / "src/aspenops_nexus/data/node-registry.json"
    point_counts = [10] if smoke else [1, 10, 100, 1000]
    worker_counts = [1, 2] if smoke else [1, 2, 4, 8]
    measurements: list[Measurement] = []
    for points in point_counts:
        for workers in worker_counts:
            measurements.append(
                measure_pool(
                    scenario="worker_matrix",
                    model_path=model_path,
                    registry_path=registry_path,
                    points=points,
                    workers=workers,
                )
            )
    if not smoke:
        for ratio in (0.0, 0.25, 0.75):
            measurements.append(
                measure_pool(
                    scenario="duplicate_ratio",
                    model_path=model_path,
                    registry_path=registry_path,
                    points=100,
                    workers=4,
                    duplicate_ratio=ratio,
                )
            )
        for warm in (False, True):
            measurements.append(
                measure_pool(
                    scenario="cache",
                    model_path=model_path,
                    registry_path=registry_path,
                    points=100,
                    workers=4,
                    warm_cache=warm,
                )
            )
        measurements.append(
            measure_pool(
                scenario="nonconvergence",
                model_path=model_path,
                registry_path=registry_path,
                points=20,
                workers=2,
                failing=True,
            )
        )
    return {
        "schema": "aspenops.benchmark-matrix/v1",
        "kind": "portable-mock-orchestration",
        "boundary": (
            "These measurements characterize portable orchestration only. They are not Aspen "
            "Plus/HYSYS performance or physical-validation evidence."
        ),
        "repo_root": str(repo_root),
        "smoke": smoke,
        "measurements": [asdict(item) for item in measurements],
        "sequential_jobs": sequential_job_measurement(
            model_path=model_path,
            registry_path=registry_path,
            workers=2,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    result = run_matrix(Path(args.repo_root).resolve(), smoke=args.smoke)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
