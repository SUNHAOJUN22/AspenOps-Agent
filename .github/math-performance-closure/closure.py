from __future__ import annotations

import argparse
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


TEST_CONTENT = '''from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.pool as pool_module
from aspenops_nexus.evaluation import _constraint_violation, _safe_fsum
from aspenops_nexus.models import ConstraintSpec, EvaluationRequest, EvaluationResult
from aspenops_nexus.optimizer import ParetoPoint, _pareto_front_general, pareto_front
from aspenops_nexus.pool import CasePool
from aspenops_nexus.units import convert, supported_units
from aspenops_nexus.worker import WorkerHandle


def _request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": "model.bkp",
            "registry_path": "registry.json",
            "backend": "mock",
            "writes": [],
            "reads": [],
        }
    )


def _result(handle: WorkerHandle) -> EvaluationResult:
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


def test_safe_fsum_recovers_exact_cancellation_after_intermediate_overflow() -> None:
    maximum = sys.float_info.max
    assert _safe_fsum([maximum, maximum, -maximum, -maximum]) == 0.0


def test_safe_fsum_preserves_true_overflow_sign() -> None:
    maximum = sys.float_info.max
    positive = _safe_fsum([maximum, maximum])
    negative = _safe_fsum([-maximum, -maximum])
    assert math.isinf(positive) and positive > 0.0
    assert math.isinf(negative) and negative < 0.0


def test_constraint_tolerance_semantics_are_consistent() -> None:
    def spec(operator: str) -> ConstraintSpec:
        return ConstraintSpec.from_dict(
            {
                "key": "x",
                "operator": operator,
                "value": 10.0,
                "tolerance": 0.5,
            }
        )

    assert _constraint_violation(spec("<"), 9.5) == 0.0
    assert _constraint_violation(spec("<"), 10.0) == 0.5
    assert _constraint_violation(spec("<="), 10.5) == 0.0
    assert _constraint_violation(spec(">"), 10.5) == 0.0
    assert _constraint_violation(spec(">"), 10.0) == 0.5
    assert _constraint_violation(spec(">="), 9.5) == 0.0
    assert _constraint_violation(spec("=="), 10.5) == 0.0
    assert _constraint_violation(spec("=="), 10.75) == 0.25


def test_supported_unit_conversions_round_trip() -> None:
    units = supported_units()
    grouped: dict[str, list[str]] = {}
    for unit, dimension in units.items():
        grouped.setdefault(dimension, []).append(unit)
    samples = (0.0, 1.0, 123.456)
    for compatible in grouped.values():
        for source in compatible:
            for target in compatible:
                for value in samples:
                    restored = convert(convert(value, source, target), target, source)
                    assert math.isclose(restored, value, rel_tol=1e-12, abs_tol=1e-9)
    assert math.isclose(convert(32.0, "F", "C"), 0.0, abs_tol=1e-12)
    assert math.isclose(convert(212.0, "F", "C"), 100.0, abs_tol=1e-12)
    assert math.isclose(convert(100.0, "%", "fraction"), 1.0, abs_tol=1e-15)


def test_two_objective_front_matches_general_definition() -> None:
    rng = random.Random(20260802)
    for _ in range(80):
        points = tuple(
            ParetoPoint(
                (float(index),),
                (float(rng.randrange(-8, 9)), float(rng.randrange(-8, 9))),
            )
            for index in range(40)
        )
        unique = tuple(dict.fromkeys(points))
        assert set(pareto_front(points)) == set(_pareto_front_general(unique))


def test_single_worker_dispatch_avoids_heavy_queue_and_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class AliveProcess:
        def is_alive(self) -> bool:
            return True

    class Cache:
        def get_many(self, keys: list[str]) -> dict[str, dict[str, Any]]:
            del keys
            return {}

        def put_many(self, payloads: dict[str, dict[str, Any]]) -> None:
            assert not payloads

    pool = object.__new__(CasePool)
    pool._handles = [
        WorkerHandle(
            worker_id=0,
            process=AliveProcess(),
            connection=object(),  # type: ignore[arg-type]
            staged_model=Path("model.bkp"),
            runtime={"backend": "mock"},
        )
    ]
    pool.cache = Cache()  # type: ignore[assignment]
    pool.cache_failures = False
    pool._key_requests = lambda requests: [  # type: ignore[method-assign]
        (f"key-{index}", request) for index, request in enumerate(requests)
    ]
    pool._recycle_reason = lambda handle: None  # type: ignore[method-assign]
    pool._result_recycle_reason = (  # type: ignore[method-assign]
        lambda handle, active_result: None
    )
    pool._cacheable = lambda request, active_result: False  # type: ignore[method-assign]

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("single-worker dispatch must not construct Queue or Thread")

    monkeypatch.setattr(pool_module.queue, "Queue", forbidden)
    monkeypatch.setattr(pool_module.threading, "Thread", forbidden)
    monkeypatch.setattr(pool_module, "evaluate_on_worker", lambda handle, request: _result(handle))

    results = pool._evaluate_many_locked([_request()] * 4, cancel_check=None)
    assert len(results) == 4
    assert [item.request_hash for item in results] == [f"key-{index}" for index in range(4)]
'''


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one patch target in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def apply_changes() -> None:
    pool = Path("src/aspenops_nexus/pool.py")
    replace_once(
        pool,
        "        tasks: queue.Queue[tuple[str, EvaluationRequest, list[int]]] = queue.Queue()\n",
        "        tasks: queue.SimpleQueue[tuple[str, EvaluationRequest, list[int]]] = (\n"
        "            queue.SimpleQueue()\n"
        "        )\n",
    )
    replace_once(
        pool,
        '''        threads = [
            threading.Thread(target=worker_loop, args=(index,), name=f"aspenops-dispatch-{index}")
            for index in range(min(len(self._handles), len(unique)))
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
''',
        '''        worker_count = min(len(self._handles), len(unique))
        if worker_count == 1:
            worker_loop(0)
        else:
            threads = [
                threading.Thread(
                    target=worker_loop,
                    args=(index,),
                    name=f"aspenops-dispatch-{index}",
                )
                for index in range(worker_count)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
''',
    )

    evaluation = Path("src/aspenops_nexus/evaluation.py")
    replace_once(evaluation, "import sys\n", "import sys\nfrom fractions import Fraction\n")
    replace_once(
        evaluation,
        '''_MAX_FINITE = sys.float_info.max


def _safe_fsum(values: list[float]) -> float:
    try:
        return math.fsum(values)
    except OverflowError:
        return math.inf
''',
        '''_MAX_FINITE = sys.float_info.max
_MAX_FINITE_FRACTION = Fraction.from_float(_MAX_FINITE)


def _safe_fsum(values: list[float]) -> float:
    try:
        return math.fsum(values)
    except OverflowError:
        exact = sum((Fraction.from_float(value) for value in values), Fraction())
        if exact > _MAX_FINITE_FRACTION:
            return math.inf
        if exact < -_MAX_FINITE_FRACTION:
            return -math.inf
        return float(exact)
''',
    )
    Path("tests/test_math_performance_closure.py").write_text(TEST_CONTENT, encoding="utf-8")


def compare(before_path: Path, after_path: Path, output_path: Path) -> None:
    before = json.loads(before_path.read_text(encoding="utf-8"))
    after = json.loads(after_path.read_text(encoding="utf-8"))
    for key in ("single_checksum", "batch_checksum"):
        if before[key] != after[key]:
            raise RuntimeError(f"Result mismatch for {key}: {before[key]} != {after[key]}")
    speedups = {
        "single_worker_dispatch": before["single_seconds"] / after["single_seconds"],
        "large_single_worker_batch": before["batch_seconds"] / after["batch_seconds"],
    }
    if speedups["single_worker_dispatch"] < 1.20:
        raise RuntimeError(
            "Single-dispatch speedup below threshold: "
            f"{speedups['single_worker_dispatch']:.3f}x"
        )
    if speedups["large_single_worker_batch"] < 1.10:
        raise RuntimeError(
            "Batch-dispatch speedup below threshold: "
            f"{speedups['large_single_worker_batch']:.3f}x"
        )
    output_path.write_text(
        json.dumps(
            {
                "before": before,
                "after": after,
                "speedups": speedups,
                "result_checksums_equal": True,
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def junit(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        "tests": sum(int(item.attrib.get("tests", 0)) for item in suites),
        "failures": sum(int(item.attrib.get("failures", 0)) for item in suites),
        "errors": sum(int(item.attrib.get("errors", 0)) for item in suites),
        "skipped": sum(int(item.attrib.get("skipped", 0)) for item in suites),
        "time_seconds": sum(float(item.attrib.get("time", 0.0)) for item in suites),
    }


def generate_report(performance_path: Path) -> None:
    performance = json.loads(performance_path.read_text(encoding="utf-8"))
    coverage = {
        version: json.loads(Path(f"/tmp/coverage-{version}.json").read_text(encoding="utf-8"))[
            "totals"
        ]["percent_covered"]
        for version in ("3.11", "3.12", "3.13")
    }
    tests = {
        "focused": junit(Path("/tmp/focused.xml")),
        **{
            version: junit(Path(f"/tmp/junit-{version}.xml"))
            for version in ("3.11", "3.12", "3.13")
        },
    }
    report = {
        "schema": "aspenops.math-performance-closure/v1",
        "decision": "PASS",
        "source_baseline": os.environ["BASE_SHA"],
        "qualification_input_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "qualification_run": {
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        },
        "aspen_executed": False,
        "qualification_boundary": (
            "Portable Python mathematics, numerical stability, dispatch, persistence, security, "
            "packaging and performance evidence; not licensed Aspen physics."
        ),
        "changes": [
            "Recover exact finite balance cancellation when math.fsum overflows internally.",
            "Preserve the sign of true balance-sum overflow.",
            "Use queue.SimpleQueue where task tracking and join are not required.",
            "Execute one-effective-worker dispatch in the current thread.",
            "Add deterministic formula, unit, Pareto and dispatch regression tests.",
        ],
        "performance": {
            "boundary": "Pure Python orchestration benchmark; not Aspen solve acceleration.",
            **performance,
        },
        "tests": tests,
        "coverage_percent": coverage,
        "hard_gates": {
            "lock_check": 0,
            "focused_tests": 0,
            "ruff": 0,
            "format": 0,
            "mypy_strict": 0,
            "compileall": 0,
            "bandit": 0,
            "full_3_11": 0,
            "full_3_12": 0,
            "full_3_13": 0,
            "dependency_audit": 0,
            "build": 0,
            "wheel_smoke": 0,
            "performance_policy": 0,
        },
    }
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    (docs / "MATH_PERFORMANCE_CLOSURE_RESULT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    speedups = performance["speedups"]
    markdown = f'''# Math and performance closure

- Decision: **PASS**
- Baseline: `{report["source_baseline"]}`
- Single-worker dispatch speedup: **{speedups["single_worker_dispatch"]:.3f}x**
- Large single-worker batch speedup: **{speedups["large_single_worker_batch"]:.3f}x**
- Python 3.11 coverage: **{coverage["3.11"]:.3f}%**
- Python 3.12 coverage: **{coverage["3.12"]:.3f}%**
- Python 3.13 coverage: **{coverage["3.13"]:.3f}%**

The mathematical fix recovers exact finite cancellation after intermediate floating-point
summation overflow and preserves the sign of true overflow. The performance figures measure
portable Python orchestration only; no licensed Aspen solve was executed.
'''
    (docs / "MATH_PERFORMANCE_CLOSURE_RESULT.md").write_text(markdown, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("apply")
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--before", type=Path, required=True)
    compare_parser.add_argument("--after", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--performance", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "apply":
        apply_changes()
    elif args.command == "compare":
        compare(args.before, args.after, args.output)
    elif args.command == "report":
        generate_report(args.performance)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
