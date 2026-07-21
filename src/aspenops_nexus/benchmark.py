from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from .models import EvaluationRequest, VariableRead, VariableWrite
from .pool import CasePool


def benchmark_worker_matrix(
    *,
    model_path: Path,
    registry_path: Path,
    points: int,
    worker_candidates: list[int],
    state_dir: Path,
) -> dict[str, Any]:
    if points < 1:
        raise ValueError("points must be positive")
    if not worker_candidates:
        raise ValueError("worker_candidates must not be empty")
    if any(workers < 1 for workers in worker_candidates):
        raise ValueError("worker candidates must be positive")

    state_dir = state_dir.expanduser().resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    measurements: list[dict[str, Any]] = []
    requests = [
        EvaluationRequest(
            model_path=str(model_path),
            registry_path=str(registry_path),
            backend="mock",
            writes=(
                VariableWrite("stream.input.temperature", {"stream": "FEED"}, 40.0 + i * 2, "C"),
                VariableWrite("block.input.reflux_ratio", {"block": "COL1"}, 1.2 + 0.03 * i, "1"),
            ),
            reads=(
                VariableRead("stream.output.purity", {"stream": "PRODUCT"}, "fraction"),
                VariableRead("block.output.reboiler_duty", {"block": "COL1"}, "kW"),
            ),
            timeout_s=30,
        )
        for i in range(points)
    ]
    for workers in worker_candidates:
        with tempfile.TemporaryDirectory(
            prefix="aspenops-benchmark-",
            dir=state_dir,
        ) as temporary:
            cache_path = Path(temporary) / "cache.sqlite3"
            started = time.perf_counter()
            with CasePool(
                backend_name="mock",
                model_path=model_path,
                registry_path=registry_path,
                workers=workers,
                visible=False,
                cache_path=cache_path,
            ) as pool:
                results = pool.evaluate_many(requests)
            elapsed = max(time.perf_counter() - started, 1e-12)
        latencies = [result.elapsed_s for result in results]
        measurements.append(
            {
                "workers": workers,
                "elapsed_s": elapsed,
                "throughput_points_s": points / elapsed,
                "p50_point_s": statistics.median(latencies),
                "p95_point_s": sorted(latencies)[max(0, int(0.95 * len(latencies)) - 1)],
                "ok_points": sum(1 for result in results if result.ok),
            }
        )
    recommended = max(measurements, key=lambda item: item["throughput_points_s"])["workers"]
    return {
        "kind": "portable_mock_worker_matrix",
        "points": points,
        "measurements": measurements,
        "recommended_workers": recommended,
        "production_bound": (
            "min(measured recommendation, configured license slots, "
            "stable Aspen instances, host capacity)"
        ),
    }
