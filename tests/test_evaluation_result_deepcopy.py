from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import aspenops_nexus.models as models_module
from aspenops_nexus.models import EvaluationResult

ROOT = Path(__file__).resolve().parents[1]


def _result() -> EvaluationResult:
    shared: dict[str, Any] = {"items": [1, 2, 3]}
    return EvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values={"shared": shared},
        units={"shared": "fraction"},
        violations=["example"],
        diagnostics={"shared": shared},
        elapsed_s=0.1,
        balance_residuals={"mass": {"relative": 0.0, "passed": 1.0}},
        request_hash="hash",
        worker_id=3,
    )


def test_evaluation_result_deepcopy_preserves_aliases_cycles_and_isolation() -> None:
    result = _result()
    result.diagnostics["cycle"] = result
    clone = deepcopy(result)

    assert clone is not result
    assert clone.values["shared"] is clone.diagnostics["shared"]
    assert clone.diagnostics["cycle"] is clone
    assert clone.units is not result.units
    assert clone.violations is not result.violations
    assert clone.balance_residuals is not result.balance_residuals
    assert clone.balance_residuals["mass"] is not result.balance_residuals["mass"]

    clone.values["shared"]["items"].append(4)
    clone.units["shared"] = None
    clone.violations.append("mutated")
    clone.balance_residuals["mass"]["relative"] = 1.0
    assert result.values["shared"]["items"] == [1, 2, 3]
    assert result.units["shared"] == "fraction"
    assert result.violations == ["example"]
    assert result.balance_residuals["mass"]["relative"] == 0.0


def test_evaluation_result_deepcopy_only_recurses_into_unbounded_payloads(
    monkeypatch: Any,
) -> None:
    result = _result()
    original_deepcopy = models_module.deepcopy
    copied: list[object] = []

    def counted(value: object, memo: dict[int, object]) -> object:
        copied.append(value)
        return original_deepcopy(value, memo)

    monkeypatch.setattr(models_module, "deepcopy", counted)
    clone = deepcopy(result)
    assert copied == [result.values, result.diagnostics]
    monkeypatch.setattr(models_module, "deepcopy", original_deepcopy)
    assert clone.to_dict() == result.to_dict()


def test_result_deepcopy_benchmark_meets_performance_floor() -> None:
    output = (
        ROOT
        / "var/ci"
        / (f"result-deepcopy-benchmark-py{sys.version_info.major}.{sys.version_info.minor}.json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("COV_CORE") or key.startswith("COVERAGE") or key == "PYTHONTRACEMALLOC":
            environment.pop(key, None)
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/benchmark_result_deepcopy.py"),
            "--output",
            str(output),
            "--min-speedup",
            "1.25",
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
    assert payload["speedup"] >= 1.25
