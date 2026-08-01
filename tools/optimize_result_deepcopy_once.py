from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one patch anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_models() -> None:
    path = Path("src/aspenops_nexus/models.py")
    replace_once(
        path,
        "import math\nfrom dataclasses import asdict, dataclass, field\n",
        "import math\nfrom copy import deepcopy\nfrom dataclasses import asdict, dataclass, field\n",
    )
    anchor = (
        "    def to_dict(self) -> dict[str, Any]:\n"
        "        return asdict(self)\n"
    )
    method = (
        "    def __deepcopy__(self, memo: dict[int, Any]) -> EvaluationResult:\n"
        "        \"\"\"Clone mutable result payloads without generic dataclass reconstruction.\"\"\"\n"
        "        existing = memo.get(id(self))\n"
        "        if existing is not None:\n"
        "            return cast(EvaluationResult, existing)\n"
        "\n"
        "        clone = object.__new__(EvaluationResult)\n"
        "        memo[id(self)] = clone\n"
        "        clone.ok = self.ok\n"
        "        clone.communication_ok = self.communication_ok\n"
        "        clone.engine_ok = self.engine_ok\n"
        "        clone.converged = self.converged\n"
        "        clone.feasible = self.feasible\n"
        "        clone.values = deepcopy(self.values, memo)\n"
        "        clone.units = self.units.copy()\n"
        "        clone.violations = self.violations.copy()\n"
        "        clone.diagnostics = deepcopy(self.diagnostics, memo)\n"
        "        clone.elapsed_s = self.elapsed_s\n"
        "        clone.balance_residuals = {\n"
        "            name: detail.copy() for name, detail in self.balance_residuals.items()\n"
        "        }\n"
        "        clone.cache_source = self.cache_source\n"
        "        clone.cache_hit = self.cache_hit\n"
        "        clone.request_hash = self.request_hash\n"
        "        clone.worker_id = self.worker_id\n"
        "        return clone\n"
        "\n"
        "    def to_dict(self) -> dict[str, Any]:\n"
        "        return asdict(self)\n"
    )
    replace_once(path, anchor, method)


def write_benchmark() -> None:
    content = dedent(
        '''
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
            legacy_seconds = _measure(
                lambda: deepcopy(legacy), iterations=iterations, repeats=repeats
            )
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
                    "Portable Python EvaluationResult cloning benchmark; "
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
        '''
    ).lstrip()
    Path("scripts/benchmark_result_deepcopy.py").write_text(content, encoding="utf-8")


def write_tests() -> None:
    content = dedent(
        '''
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
            assert clone.to_dict() == result.to_dict()
            assert copied == [result.values, result.diagnostics]


        def test_result_deepcopy_benchmark_meets_performance_floor() -> None:
            output = ROOT / "var/ci" / (
                f"result-deepcopy-benchmark-py{sys.version_info.major}.{sys.version_info.minor}.json"
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            environment = os.environ.copy()
            for key in tuple(environment):
                if key.startswith("COV_CORE") or key.startswith("COVERAGE"):
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
        '''
    ).lstrip()
    Path("tests/test_evaluation_result_deepcopy.py").write_text(content, encoding="utf-8")


def main() -> None:
    patch_models()
    write_benchmark()
    write_tests()


if __name__ == "__main__":
    main()
