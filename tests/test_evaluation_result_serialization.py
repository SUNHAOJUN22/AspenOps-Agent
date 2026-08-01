from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from aspenops_nexus.models import EvaluationResult

ROOT = Path(__file__).resolve().parents[1]


def _result() -> EvaluationResult:
    return EvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values={"nested": {"items": [1, 2]}},
        units={"nested": None},
        violations=["original"],
        diagnostics={"worker": {"runtime": {"build": 1}}},
        elapsed_s=0.25,
        balance_residuals={"mass": {"residual": 0.0, "passed": 1.0}},
        request_hash="abc",
        worker_id=2,
    )


def test_result_serialization_round_trip_and_isolation() -> None:
    result = _result()
    payload = result.to_dict()
    assert EvaluationResult.from_dict(payload) == result

    payload["values"]["nested"]["items"].append(3)
    payload["violations"].append("mutated")
    payload["diagnostics"]["worker"]["runtime"]["build"] = 2
    payload["balance_residuals"]["mass"]["residual"] = 1.0

    assert result.values == {"nested": {"items": [1, 2]}}
    assert result.violations == ["original"]
    assert result.diagnostics == {"worker": {"runtime": {"build": 1}}}
    assert result.balance_residuals == {"mass": {"residual": 0.0, "passed": 1.0}}


def test_result_serialization_benchmark_meets_floor() -> None:
    output = (
        ROOT
        / "var/ci"
        / (
            f"result-serialization-benchmark-py{sys.version_info.major}."
            f"{sys.version_info.minor}.json"
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("COV_CORE") or key.startswith("COVERAGE") or key == "PYTHONTRACEMALLOC":
            environment.pop(key, None)
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/benchmark_result_serialization.py"),
            "--output",
            str(output),
            "--iterations",
            "1_000",
            "--repeats",
            "5",
            "--min-speedup",
            "1.10",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decision"] == "PASS"
    assert payload["equivalent"] is True
    assert payload["deep_isolation"] is True
    assert payload["speedup"] >= 1.10
