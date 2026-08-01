from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from aspenops_nexus.models import EvaluationResult


@dataclass(slots=True)
class _LegacyEvaluationResult:
    ok: bool
    communication_ok: bool
    engine_ok: bool
    converged: bool
    feasible: bool
    values: dict[str, Any]
    units: dict[str, str | None]
    violations: list[str]
    diagnostics: dict[str, Any]
    elapsed_s: float
    balance_residuals: dict[str, dict[str, float]] = field(default_factory=dict)
    cache_source: str = "computed"
    cache_hit: bool = False
    request_hash: str = ""
    worker_id: int | None = None


def _documents() -> tuple[_LegacyEvaluationResult, EvaluationResult]:
    legacy = _LegacyEvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values={"stream.output.purity:stream=PRODUCT": 0.99},
        units={"stream.output.purity:stream=PRODUCT": "fraction"},
        violations=[],
        diagnostics={"nested": {"value": 1}},
        elapsed_s=0.001,
        balance_residuals={
            "mass": {
                "residual": 0.0,
                "absolute": 0.0,
                "scale": 1.0,
                "relative": 0.0,
                "passed": 1.0,
            }
        },
        request_hash="a" * 64,
        worker_id=0,
    )
    optimized = EvaluationResult(**asdict(legacy))
    return legacy, optimized


def _measure(function: Any, *, iterations: int, repeats: int) -> float:
    for _ in range(1_000):
        function()
    samples: list[float] = []
    gc_was_enabled = gc.isenabled()
    try:
        gc.disable()
        for _ in range(repeats):
            started = time.perf_counter()
            for _ in range(iterations):
                function()
            samples.append(time.perf_counter() - started)
    finally:
        if gc_was_enabled:
            gc.enable()
    return statistics.median(samples)


def run(*, iterations: int, repeats: int, minimum_speedup: float) -> dict[str, Any]:
    legacy, optimized = _documents()
    legacy_seconds = _measure(lambda: deepcopy(legacy), iterations=iterations, repeats=repeats)
    optimized_seconds = _measure(
        lambda: deepcopy(optimized), iterations=iterations, repeats=repeats
    )
    legacy_clone = deepcopy(legacy)
    optimized_clone = deepcopy(optimized)
    equivalent = asdict(legacy_clone) == optimized_clone.to_dict()

    optimized_clone.values["stream.output.purity:stream=PRODUCT"] = 0.5
    optimized_clone.diagnostics["nested"]["value"] = 99
    optimized_clone.balance_residuals["mass"]["relative"] = 1.0
    isolated = (
        optimized.values["stream.output.purity:stream=PRODUCT"] == 0.99
        and optimized.diagnostics["nested"]["value"] == 1
        and optimized.balance_residuals["mass"]["relative"] == 0.0
    )
    speedup = legacy_seconds / optimized_seconds
    passed = equivalent and isolated and speedup >= minimum_speedup
    return {
        "schema": "aspenops.result-deepcopy-benchmark/v1",
        "decision": "PASS" if passed else "FAIL",
        "boundary": (
            "Portable Python EvaluationResult cloning benchmark; not licensed Aspen solve evidence."
        ),
        "iterations": iterations,
        "repeats": repeats,
        "legacy_seconds": legacy_seconds,
        "optimized_seconds": optimized_seconds,
        "speedup": speedup,
        "minimum_speedup": minimum_speedup,
        "equivalent": equivalent,
        "deep_isolation": isolated,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--min-speedup", type=float, default=1.5)
    args = parser.parse_args()
    result = run(
        iterations=args.iterations,
        repeats=args.repeats,
        minimum_speedup=args.min_speedup,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    if result["decision"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
