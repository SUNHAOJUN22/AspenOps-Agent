from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    module: str
    arguments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StartupMeasurement:
    scenario: str
    module: str
    arguments: tuple[str, ...]
    trial_count: int
    warmup_count: int
    median_s: float
    p95_s: float
    min_s: float
    max_s: float
    coefficient_of_variation: float
    samples_s: tuple[float, ...]


def percentile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, round(probability * len(ordered)))
    return ordered[min(len(ordered), rank) - 1]


def run_once(scenario: Scenario) -> float:
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-m", scenario.module, *scenario.arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"{scenario.name} failed with {completed.returncode}: {completed.stderr[-1000:]}"
        )
    return elapsed


def measure(scenario: Scenario, *, trials: int, warmups: int) -> StartupMeasurement:
    for _ in range(warmups):
        run_once(scenario)
    samples = [run_once(scenario) for _ in range(trials)]
    mean = statistics.fmean(samples)
    coefficient = 0.0 if trials < 2 or mean == 0.0 else statistics.pstdev(samples) / mean
    return StartupMeasurement(
        scenario=scenario.name,
        module=scenario.module,
        arguments=scenario.arguments,
        trial_count=trials,
        warmup_count=warmups,
        median_s=statistics.median(samples),
        p95_s=percentile(samples, 0.95),
        min_s=min(samples),
        max_s=max(samples),
        coefficient_of_variation=coefficient,
        samples_s=tuple(samples),
    )


def environment() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    return {
        "git_commit": os.getenv("GITHUB_SHA") or os.getenv("ASPENOPS_GIT_COMMIT"),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_logical": psutil.cpu_count(logical=True),
        "cpu_physical": psutil.cpu_count(logical=False),
        "memory_total_bytes": int(memory.total),
    }


def comparison(
    measurements: list[StartupMeasurement],
    candidate: str,
    control: str,
) -> dict[str, Any]:
    by_name = {item.scenario: item for item in measurements}
    candidate_value = by_name[candidate].median_s
    control_value = by_name[control].median_s
    saved = control_value - candidate_value
    return {
        "candidate": candidate,
        "control": control,
        "candidate_median_s": candidate_value,
        "control_median_s": control_value,
        "absolute_saved_s": saved,
        "relative_saved_fraction": None if control_value == 0.0 else saved / control_value,
        "classification": "MEASURED_SAME_ENVIRONMENT",
    }


def run_probe(*, trials: int, warmups: int) -> dict[str, Any]:
    if trials < 1:
        raise ValueError("trials must be positive")
    if warmups < 0:
        raise ValueError("warmups must be non-negative")
    scenarios = [
        Scenario("bootstrap_version", "aspenops_nexus.cli_bootstrap", ("--version",)),
        Scenario("full_cli_version", "aspenops_nexus.cli", ("--version",)),
        Scenario("bootstrap_help", "aspenops_nexus.cli_bootstrap", ("--help",)),
        Scenario("full_cli_help", "aspenops_nexus.cli", ("--help",)),
        Scenario(
            "bootstrap_optimize_help",
            "aspenops_nexus.cli_bootstrap",
            ("optimize", "--help"),
        ),
        Scenario("full_cli_optimize_help", "aspenops_nexus.cli", ("optimize", "--help")),
    ]
    measurements = [measure(item, trials=trials, warmups=warmups) for item in scenarios]
    return {
        "schema": "aspenops.cli-startup/v1",
        "kind": "portable-python-cli-startup",
        "boundary": (
            "These measurements compare Python CLI import and parser startup only. They do not "
            "measure Aspen Plus/HYSYS model open, solve, convergence or engineering performance."
        ),
        "environment": environment(),
        "measurements": [asdict(item) for item in measurements],
        "comparisons": [
            comparison(measurements, "bootstrap_version", "full_cli_version"),
            comparison(measurements, "bootstrap_help", "full_cli_help"),
            comparison(
                measurements,
                "bootstrap_optimize_help",
                "full_cli_optimize_help",
            ),
        ],
        "gate": (
            "Wall-clock startup on shared runners is recorded as evidence but is not a narrow "
            "hard regression gate. Module-import contracts are enforced separately by tests."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--trials", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=2)
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    result = run_probe(trials=args.trials, warmups=args.warmups)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
