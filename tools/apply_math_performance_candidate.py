from __future__ import annotations

import runpy
from pathlib import Path
from textwrap import dedent


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one target in {path}, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_to_dict() -> None:
    path = Path("src/aspenops_nexus/models.py")
    replace_once(
        path,
        "from dataclasses import asdict, dataclass, field\n",
        "from dataclasses import dataclass, field\n",
    )
    replace_once(
        path,
        """    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
""",
        """    def to_dict(self) -> dict[str, Any]:
        \"\"\"Serialize JSON-like fields without generic dataclass traversal.\"\"\"
        return {
            \"ok\": self.ok,
            \"communication_ok\": self.communication_ok,
            \"engine_ok\": self.engine_ok,
            \"converged\": self.converged,
            \"feasible\": self.feasible,
            \"values\": deepcopy(self.values),
            \"units\": self.units.copy(),
            \"violations\": self.violations.copy(),
            \"diagnostics\": deepcopy(self.diagnostics),
            \"elapsed_s\": self.elapsed_s,
            \"balance_residuals\": {
                name: detail.copy() for name, detail in self.balance_residuals.items()
            },
            \"cache_source\": self.cache_source,
            \"cache_hit\": self.cache_hit,
            \"request_hash\": self.request_hash,
            \"worker_id\": self.worker_id,
        }
""",
    )


def patch_deepcopy_test() -> None:
    path = Path("tests/test_evaluation_result_deepcopy.py")
    replace_once(
        path,
        """    clone = deepcopy(result)
    assert clone.to_dict() == result.to_dict()
    assert copied == [result.values, result.diagnostics]
""",
        """    clone = deepcopy(result)
    assert copied == [result.values, result.diagnostics]
    monkeypatch.setattr(models_module, \"deepcopy\", original_deepcopy)
    assert clone.to_dict() == result.to_dict()
""",
    )


def write_serialization_benchmark() -> None:
    content = dedent(
        '''
        from __future__ import annotations

        import argparse
        import gc
        import json
        import statistics
        import time
        from dataclasses import asdict, dataclass, field
        from pathlib import Path
        from typing import Any, Callable

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
                    {"name": f"c{index}", "actual": index * 0.1, "violation": 0.0}
                    for index in range(48)
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
        '''
    ).lstrip()
    Path("scripts/benchmark_result_serialization.py").write_text(content, encoding="utf-8")


def write_serialization_tests() -> None:
    content = dedent(
        '''
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
            output = ROOT / "var/ci" / (
                f"result-serialization-benchmark-py{sys.version_info.major}."
                f"{sys.version_info.minor}.json"
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            environment = os.environ.copy()
            for key in tuple(environment):
                if key.startswith("COV_CORE") or key.startswith("COVERAGE"):
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
        '''
    ).lstrip()
    Path("tests/test_evaluation_result_serialization.py").write_text(content, encoding="utf-8")


def main() -> None:
    runpy.run_path("tools/optimize_result_deepcopy_once.py", run_name="__main__")
    patch_to_dict()
    patch_deepcopy_test()
    write_serialization_benchmark()
    write_serialization_tests()


if __name__ == "__main__":
    main()
