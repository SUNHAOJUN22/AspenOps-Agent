from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from collections.abc import Callable
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
    values = {f"value_{index}": index * 0.125 for index in range(96)}
    units = {key: "kg/h" for key in values}
    diagnostics: dict[str, Any] = {
        "state_trace": ["received", "compiled", "solved", "verified"],
        "runtime": {
            "backend": "mock",
            "nested": {
                "limits": list(range(32)),
                "labels": {f"k{index}": f"v{index}" for index in range(32)},
            },
        },
        "constraints": [
            {"name": f"c{index}", "actual": index * 0.1, "violation": 0.0} for index in range(48)
        ],
    }
    balances = {
        f"balance_{index}": {
            "residual": 0.0,
            "absolute": 0.0,
            "scale": float(index + 1),
            "relative": 0.0,
            "abs_tol": 1e-6,
            "rel_tol": 1e-6,
            "passed": 1.0,
        }
        for index in range(24)
    }
    legacy = _LegacyEvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values=values,
        units=units,
        violations=[],
        diagnostics=diagnostics,
        elapsed_s=0.125,
        balance_residuals=balances,
        request_hash="a" * 64,
        worker_id=3,
    )
    optimized = EvaluationResult(**asdict(legacy))
    return legacy, optimized


def _measure(function: Callable[[], object], iterations: int, repeats: int) -> float:
    samples: list[float] = []
    checksum = 0
    gc_was_enabled = gc.isenabled()
    try:
        gc.disable()
        for _ in range(repeats):
            started = time.perf_counter()
            for _ in range(iterations):
                value = function()
                checksum ^= id(value)
            samples.append(time.perf_counter() - started)
    finally:
        if gc_was_enabled:
            gc.enable()
    if checksum == -1:
        raise AssertionError("unreachable checksum")
    return statistics.median(samples)


def run(*, iterations: int, repeats: int, minimum_speedup: float) -> dict[str, Any]:
    legacy, optimized = _documents()
    legacy_payload = asdict(legacy)
    optimized_payload = optimized.to_dict()
    equivalent = legacy_payload == optimized_payload

    optimized_payload["values"]["value_0"] = -1.0
    optimized_payload["diagnostics"]["runtime"]["nested"]["limits"].append(999)
    optimized_payload["balance_residuals"]["balance_0"]["scale"] = -1.0
    isolated = (
        optimized.values["value_0"] == 0.0
        and 999 not in optimized.diagnostics["runtime"]["nested"]["limits"]
        and optimized.balance_residuals["balance_0"]["scale"] == 1.0
    )

    legacy_seconds = _measure(lambda: asdict(legacy), iterations, repeats)
    optimized_seconds = _measure(optimized.to_dict, iterations, repeats)
    speedup = legacy_seconds / optimized_seconds
    passed = equivalent and isolated and speedup >= minimum_speedup
    return {
        "schema": "aspenops.result-serialization-benchmark/v1",
        "decision": "PASS" if passed else "FAIL",
        "boundary": (
            "Portable Python EvaluationResult serialization benchmark; "
            "not licensed Aspen solve evidence."
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
    parser.add_argument("--iterations", type=int, default=2_000)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--min-speedup", type=float, default=1.25)
    args = parser.parse_args()
    result = run(
        iterations=args.iterations,
        repeats=args.repeats,
        minimum_speedup=args.min_speedup,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    if result["decision"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
