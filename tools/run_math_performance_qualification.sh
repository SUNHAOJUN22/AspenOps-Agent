#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
QUAL_DIR="var/math-performance-final"
SOURCE_BASELINE="0e12306bc49985b6a2c71d9db04ab39ed13fa15d"
mkdir -p "$QUAL_DIR"

python - <<'PY'
import subprocess

baseline = "0e12306bc49985b6a2c71d9db04ab39ed13fa15d"
allowed = {
    ".github/workflows/issue-math-performance-qualification.yml",
    ".github/workflows/math-performance-qualification-once.yml",
    ".github/workflows/optimize-result-deepcopy-once-v2.yml",
    ".github/workflows/optimize-result-deepcopy-once.yml",
    ".github/workflows/scheduled-math-performance-qualification.yml",
    "tools/apply_compensated_weighted_sum_candidate.py",
    "tools/apply_math_performance_candidate.py",
    "tools/optimize_result_deepcopy_once.py",
    "tools/run_math_performance_qualification.sh",
}
changed = set(
    subprocess.check_output(
        ["git", "diff", "--name-only", f"{baseline}..HEAD"], text=True
    ).splitlines()
)
unexpected = sorted(changed - allowed)
if unexpected:
    raise SystemExit(f"Unexpected production changes before qualification: {unexpected}")
print(f"Qualified staging boundary: {len(changed)} temporary paths, no production drift")
PY

uv lock --check
uv sync --python 3.12 --frozen --extra dev --extra agent --extra signing

python tools/apply_math_performance_candidate.py
python tools/apply_compensated_weighted_sum_candidate.py

rm -f \
  .github/workflows/issue-math-performance-qualification.yml \
  .github/workflows/math-performance-qualification-once.yml \
  .github/workflows/optimize-result-deepcopy-once-v2.yml \
  .github/workflows/optimize-result-deepcopy-once.yml \
  .github/workflows/scheduled-math-performance-qualification.yml \
  tools/apply_compensated_weighted_sum_candidate.py \
  tools/apply_math_performance_candidate.py \
  tools/optimize_result_deepcopy_once.py \
  tools/run_math_performance_qualification.sh

uv run ruff format \
  src/aspenops_nexus/models.py \
  src/aspenops_nexus/optimization.py \
  scripts/benchmark_result_deepcopy.py \
  scripts/benchmark_result_serialization.py \
  tests/test_evaluation_result_deepcopy.py \
  tests/test_evaluation_result_serialization.py \
  tests/test_weighted_sum_compensation.py
uv run ruff check --fix \
  src/aspenops_nexus/models.py \
  src/aspenops_nexus/optimization.py \
  scripts/benchmark_result_deepcopy.py \
  scripts/benchmark_result_serialization.py \
  tests/test_evaluation_result_deepcopy.py \
  tests/test_evaluation_result_serialization.py \
  tests/test_weighted_sum_compensation.py
git diff --check

uv run python - <<'PY'
import json
import math
import statistics
import sys
import time
from pathlib import Path

from aspenops_nexus.evaluation import _constraint_violation, _finite_nonnegative_sum
from aspenops_nexus.models import ConstraintSpec
from aspenops_nexus.optimization import (
    _finite_weighted_sum,
    _saturating_nonnegative_add,
)

cases = [
    ("<", 9.5, 10.0, 0.5, 0.0),
    ("<", 9.75, 10.0, 0.5, 0.25),
    ("<=", 10.5, 10.0, 0.5, 0.0),
    ("<=", 10.75, 10.0, 0.5, 0.25),
    (">", 10.5, 10.0, 0.5, 0.0),
    (">", 10.25, 10.0, 0.5, 0.25),
    (">=", 9.5, 10.0, 0.5, 0.0),
    (">=", 9.25, 10.0, 0.5, 0.25),
    ("==", 10.5, 10.0, 0.5, 0.0),
    ("==", 10.75, 10.0, 0.5, 0.25),
]
details = []
for operator, actual, limit, tolerance, expected in cases:
    spec = ConstraintSpec(
        key="x",
        identifiers={},
        operator=operator,
        value=limit,
        tolerance=tolerance,
    )
    observed = _constraint_violation(spec, actual)
    assert math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-15)
    details.append(
        {
            "operator": operator,
            "actual": actual,
            "limit": limit,
            "tolerance": tolerance,
            "violation": observed,
        }
    )

total, saturated = _finite_nonnegative_sum([sys.float_info.max, sys.float_info.max])
assert total == sys.float_info.max and saturated
assert _saturating_nonnegative_add(sys.float_info.max, 1.0) == sys.float_info.max
assert _finite_weighted_sum(((1.0, 1e16), (1.0, 1.0), (1.0, -1e16))) == 1.0
assert _finite_weighted_sum(((2.0, 1e308), (-2.0, 1e308))) == 0.0
assert _finite_weighted_sum(((2.0, 1e308), (2.0, 1e308))) == sys.float_info.max
assert _finite_weighted_sum(((-2.0, 1e308), (-2.0, 1e308))) == -sys.float_info.max

pairs = tuple((1.0, float(index + 1)) for index in range(16))
loops = 100_000
samples = []
for _ in range(7):
    started = time.perf_counter()
    for _ in range(loops):
        _finite_weighted_sum(pairs)
    samples.append(time.perf_counter() - started)
weighted_seconds = statistics.median(samples)
weighted_us_per_call = weighted_seconds * 1_000_000 / loops
assert weighted_us_per_call < 20.0

report = {
    "decision": "PASS",
    "constraint_cases": details,
    "strict_inequalities": "tolerance is a safety margin",
    "non_strict_inequalities": "tolerance is an acceptance band",
    "equality": "absolute residual <= tolerance",
    "finite_aggregation": True,
    "weighted_mixed_magnitude_result": 1.0,
    "weighted_overflow_cancellation": True,
    "weighted_overflow_saturation": True,
    "weighted_16_term_microseconds_per_call": weighted_us_per_call,
    "weighted_performance_boundary": (
        "Portable Python scalar aggregation only; Aspen solve time is not measured."
    ),
}
Path("var/math-performance-final/math-audit.json").write_text(
    json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
    encoding="utf-8",
)
print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
PY

uv run python scripts/benchmark_result_deepcopy.py \
  --output "$QUAL_DIR/result-deepcopy.json" \
  --min-speedup 1.5
uv run python scripts/benchmark_result_serialization.py \
  --output "$QUAL_DIR/result-serialization.json" \
  --min-speedup 1.25

uv run pytest -W error::ResourceWarning \
  tests/test_evaluation_result_deepcopy.py \
  tests/test_evaluation_result_serialization.py \
  tests/test_runtime_closure.py \
  tests/test_finite_aggregation.py \
  tests/test_weighted_sum_compensation.py \
  --junitxml="$QUAL_DIR/focused.xml"

uv python install 3.11 3.12 3.13
for version in 3.11 3.12 3.13; do
  uv sync --python "$version" --frozen --extra dev --extra agent --extra signing
  PYTHONTRACEMALLOC=10 uv run pytest \
    -W error::ResourceWarning \
    -W error::pytest.PytestUnraisableExceptionWarning \
    --junitxml="$QUAL_DIR/junit-${version}.xml" \
    2>&1 | tee "$QUAL_DIR/pytest-${version}.log"
done

uv sync --python 3.12 --frozen --extra dev --extra agent --extra signing
uv run pytest \
  -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:"$QUAL_DIR/coverage.json" \
  --cov-fail-under=95
uv run python scripts/run_test_order_gate.py \
  --seed 20260728 \
  --output-dir "$QUAL_DIR"
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m compileall -q src scripts
uv run python scripts/audit_source_tree.py \
  --output "$QUAL_DIR/source-tree-audit.json"
uv tool run --isolated --from 'bandit==1.9.4' bandit \
  --recursive src scripts \
  --severity-level high \
  --confidence-level high \
  --format json \
  --output "$QUAL_DIR/bandit.json"
uv run python scripts/measure_operation_counts.py \
  --output "$QUAL_DIR/operation-counts.json"
uv run python scripts/run_benchmark_matrix.py \
  --repo-root . \
  --output "$QUAL_DIR/benchmark-smoke.json" \
  --smoke
uv build

WHEEL="$(find dist -maxdepth 1 -name '*.whl' -type f | sort | tail -n 1)"
test -n "$WHEEL"
rm -rf /tmp/aspenops-wheel-venv
uv venv /tmp/aspenops-wheel-venv --python 3.12
uv pip install --python /tmp/aspenops-wheel-venv/bin/python "$WHEEL"
uv pip check --python /tmp/aspenops-wheel-venv/bin/python
/tmp/aspenops-wheel-venv/bin/python -c \
  'import aspenops_nexus; print(aspenops_nexus.__version__)'
/tmp/aspenops-wheel-venv/bin/aspenops --help >/dev/null

uv run python - <<'PY'
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path("var/math-performance-final")

def test_totals(path: Path) -> dict[str, float | int]:
    document = ET.parse(path).getroot()
    suites = list(document.iter("testsuite"))
    if not suites and document.tag == "testsuite":
        suites = [document]
    leaf_suites = [suite for suite in suites if not list(suite.findall("testsuite"))]
    active = leaf_suites or suites
    return {
        "tests": sum(int(suite.attrib.get("tests", 0)) for suite in active),
        "failures": sum(int(suite.attrib.get("failures", 0)) for suite in active),
        "errors": sum(int(suite.attrib.get("errors", 0)) for suite in active),
        "skipped": sum(int(suite.attrib.get("skipped", 0)) for suite in active),
        "time_seconds": sum(float(suite.attrib.get("time", 0.0)) for suite in active),
    }

deepcopy_benchmark = json.loads((root / "result-deepcopy.json").read_text())
serialization_benchmark = json.loads((root / "result-serialization.json").read_text())
math_audit = json.loads((root / "math-audit.json").read_text())
coverage = json.loads((root / "coverage.json").read_text())
operation_counts = json.loads((root / "operation-counts.json").read_text())
full_tests = {
    version: test_totals(root / f"junit-{version}.xml")
    for version in ("3.11", "3.12", "3.13")
}
for version, result in full_tests.items():
    assert result["failures"] == result["errors"] == result["skipped"] == 0, (
        version,
        result,
    )

report = {
    "schema": "aspenops.math-performance-qualification/v2",
    "decision": "PASS",
    "qualified_source_baseline": "0e12306bc49985b6a2c71d9db04ab39ed13fa15d",
    "workflow_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
    "aspen_executed": False,
    "dynamic_modeling_executed": False,
    "parameter_estimation_executed": False,
    "machine_learning_executed": False,
    "boundary": (
        "Portable Python numerical, copying, serialization and packaging qualification; "
        "not licensed Aspen Plus/HYSYS physical solve evidence."
    ),
    "changes": [
        "Finite weighted objectives use math.fsum before exact overflow fallback.",
        "EvaluationResult uses memo-aware field-specific deepcopy.",
        "EvaluationResult uses field-specific deeply isolated serialization.",
        "Permanent numerical and performance regression contracts were added.",
        "All temporary qualification workflows and patch tools were removed.",
    ],
    "math_audit": math_audit,
    "deepcopy_benchmark": deepcopy_benchmark,
    "serialization_benchmark": serialization_benchmark,
    "full_tests": full_tests,
    "coverage_percent": coverage["totals"]["percent_covered"],
    "operation_counts": {
        "pool": operation_counts["pool"],
        "memory_cache": operation_counts["memory_cache"],
        "cache": operation_counts["cache"],
    },
    "gates": {
        "mathematical_contracts": "PASS",
        "focused_tests": "PASS",
        "python_3_11": "PASS",
        "python_3_12": "PASS",
        "python_3_13": "PASS",
        "branch_coverage": "PASS",
        "order_independence": "PASS",
        "ruff": "PASS",
        "format": "PASS",
        "mypy_strict": "PASS",
        "compileall": "PASS",
        "source_tree_audit": "PASS",
        "bandit_high_high": "PASS",
        "operation_counts": "PASS",
        "benchmark_smoke": "PASS",
        "build": "PASS",
        "isolated_wheel_install": "PASS",
        "pip_check": "PASS",
        "cli_smoke": "PASS",
    },
    "external_gate": "PENDING_LICENSED_WINDOWS_ASPEN_ENGINEERING_CERTIFICATION",
}

docs = Path("docs")
(docs / "MATH_PERFORMANCE_QUALIFICATION_RESULT.json").write_text(
    json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
    encoding="utf-8",
)
(docs / "MATH_PERFORMANCE_QUALIFICATION_RESULT.md").write_text(
    "# Math and Performance Qualification Result\n\n"
    "Decision: **PASS**\n\n"
    f"- Compensated weighted-objective audit: `PASS`\n"
    f"- Result deepcopy speedup: `{deepcopy_benchmark['speedup']:.3f}x`\n"
    f"- Result serialization speedup: `{serialization_benchmark['speedup']:.3f}x`\n"
    f"- Python 3.11 / 3.12 / 3.13 full tests: `{full_tests}`\n"
    f"- Python 3.12 branch coverage: `{report['coverage_percent']:.3f}%`\n"
    "- Quality, security, operation-count, build and isolated-wheel gates: `PASS`\n"
    "- Licensed Windows/Aspen engineering certification: `PENDING`\n\n"
    "Performance measurements cover portable Python aggregation, copying and serialization "
    "only. They are not Aspen Plus/HYSYS solve-speed evidence.\n",
    encoding="utf-8",
)
PY

git fetch origin main
if [[ "$(git rev-parse origin/main)" != "${GITHUB_SHA:-$(git rev-parse HEAD)}" ]]; then
  echo "Remote main changed during qualification; refusing publication" >&2
  exit 1
fi

git add -A
git diff --cached --check
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git commit -m "perf: improve numerical precision and result throughput"
git push origin HEAD:main
PUBLISHED_SHA="$(git rev-parse HEAD)"

if [[ -n "${TRIGGER_ISSUE:-}" ]]; then
  gh issue comment "$TRIGGER_ISSUE" --body \
    "Qualification PASS. Published SHA: ${PUBLISHED_SHA}. Run ID: ${GITHUB_RUN_ID}."
  gh issue close "$TRIGGER_ISSUE" --reason completed
fi
gh issue comment 95 --body \
  "Closed by ${PUBLISHED_SHA}: finite weighted objectives now use compensated summation with the exact overflow fallback preserved."
gh issue close 95 --reason completed
gh issue comment 96 --body \
  "Math/performance qualification PASS. Published SHA: ${PUBLISHED_SHA}. Run ID: ${GITHUB_RUN_ID}."
gh issue close 96 --reason completed
