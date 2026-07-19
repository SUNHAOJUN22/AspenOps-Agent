from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_STABLE_TRIALS = 3
_MAX_STABLE_CV = 0.05
_MIN_STEADY_STATE_POINTS = 10


def key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item["scenario"],
        item["points"],
        item["workers"],
        item["duplicate_ratio"],
        item["cache_mode"],
    )


def percent_change(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return (after - before) / before * 100.0


def format_change(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


def regression_label(throughput_change: float | None, p95_change: float | None) -> str:
    if throughput_change is not None and throughput_change < -5.0:
        return "throughput regression >5%"
    if p95_change is not None and p95_change > 5.0:
        return "P95 regression >5%"
    return "none"


def measurement_stability(item: dict[str, Any]) -> str:
    trials = int(item.get("trial_count", 1))
    coefficient = float(item.get("throughput_cv", 0.0))
    points = int(item.get("points", 0))
    workers = max(1, int(item.get("workers", 1)))
    if trials < _STABLE_TRIALS:
        return "insufficient-trials"
    if coefficient > _MAX_STABLE_CV:
        return "unstable-cv"
    if points < max(_MIN_STEADY_STATE_POINTS, workers * 2):
        return "startup-sensitive"
    return "stable"


def regression_assessment(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    throughput_change: float | None,
    p95_change: float | None,
) -> str:
    regression = regression_label(throughput_change, p95_change)
    if regression == "none":
        return regression
    reference_stability = measurement_stability(reference)
    candidate_stability = measurement_stability(candidate)
    if reference_stability != "stable" or candidate_stability != "stable":
        return (
            f"{regression}; not-gated "
            f"({reference_stability}/{candidate_stability})"
        )
    return regression


def is_stable_regression(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    throughput_change: float | None,
    p95_change: float | None,
) -> bool:
    regression = regression_label(throughput_change, p95_change)
    return regression != "none" and regression_assessment(
        reference,
        candidate,
        throughput_change,
        p95_change,
    ) == regression


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--baseline-doc", required=True)
    parser.add_argument("--after-doc", required=True)
    parser.add_argument("--fail-on-stable-regression", action="store_true")
    args = parser.parse_args()

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))
    baseline_map = {key(item): item for item in baseline["measurements"]}
    after_map = {key(item): item for item in after["measurements"]}

    baseline_lines = [
        "# Portable performance baseline",
        "",
        "Baseline revision: `main`.",
        "",
        baseline["boundary"],
        "",
        "| Scenario | Points | Workers | Duplicate ratio | Cache | Trials | "
        "Throughput (points/s) | Throughput CV | P95 (s) | RSS delta | Stability |",
        "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in baseline["measurements"]:
        baseline_lines.append(
            "| {scenario} | {points} | {workers} | {duplicate_ratio:.0%} | {cache_mode} | "
            "{trial_count} | {throughput_points_s:.3f} | {throughput_cv:.2%} | "
            "{p95_point_s:.6f} | {rss_delta} | {stability} |".format(
                **item,
                stability=measurement_stability(item),
            )
        )

    after_lines = [
        "# Portable performance after AspenOps v2 changes",
        "",
        "Candidate revision: `agent/aspenops-v2-reliability-performance`.",
        "",
        after["boundary"],
        "",
        "| Scenario | Points | Workers | Duplicate ratio | Cache | Trials | Throughput | "
        "CV | Throughput change | P95 change | Stability | Assessment |",
        "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|",
    ]
    stable_regressions: list[str] = []
    noise_sensitive: list[str] = []
    for identity in sorted(after_map):
        candidate = after_map[identity]
        reference = baseline_map.get(identity)
        if reference is None:
            continue
        throughput_change = percent_change(
            float(reference["throughput_points_s"]),
            float(candidate["throughput_points_s"]),
        )
        p95_change = percent_change(
            float(reference["p95_point_s"]),
            float(candidate["p95_point_s"]),
        )
        stability = measurement_stability(candidate)
        assessment = regression_assessment(
            reference,
            candidate,
            throughput_change,
            p95_change,
        )
        label = (
            f"{candidate['scenario']}:{candidate['points']}pts:"
            f"{candidate['workers']}workers:{candidate['cache_mode']}"
        )
        if is_stable_regression(reference, candidate, throughput_change, p95_change):
            stable_regressions.append(f"{label}: {assessment}")
        elif regression_label(throughput_change, p95_change) != "none":
            noise_sensitive.append(f"{label}: {assessment}")
        after_lines.append(
            f"| {candidate['scenario']} | {candidate['points']} | {candidate['workers']} | "
            f"{candidate['duplicate_ratio']:.0%} | {candidate['cache_mode']} | "
            f"{candidate.get('trial_count', 1)} | {candidate['throughput_points_s']:.3f} | "
            f"{float(candidate.get('throughput_cv', 0.0)):.2%} | "
            f"{format_change(throughput_change)} | {format_change(p95_change)} | "
            f"{stability} | {assessment} |"
        )

    after_lines.extend(
        [
            "",
            "## Regression gate",
            "",
            f"Stable regressions above 5%: `{len(stable_regressions)}`.",
            f"Noise-sensitive observations above 5%: `{len(noise_sensitive)}`.",
            "",
            "Stable regressions fail the performance workflow when "
            "`--fail-on-stable-regression` is enabled. Startup-sensitive, high-CV, or "
            "insufficient-trial observations remain visible but are not treated as "
            "steady-state evidence.",
            "",
            "### Stable regressions",
            "",
            *(stable_regressions or ["None."]),
            "",
            "### Noise-sensitive observations",
            "",
            *(noise_sensitive or ["None."]),
            "",
            "## Persistent sequential-job execution",
            "",
            "```json",
            json.dumps(after.get("sequential_jobs"), indent=2, ensure_ascii=False),
            "```",
            "",
            "## Interpretation boundary",
            "",
            "A positive portable throughput change is evidence about Python orchestration, "
            "deduplication, cache and persistent Worker reuse only. Licensed Aspen performance "
            "must be measured separately on an approved Windows host.",
        ]
    )

    Path(args.baseline_doc).write_text("\n".join(baseline_lines) + "\n", encoding="utf-8")
    Path(args.after_doc).write_text("\n".join(after_lines) + "\n", encoding="utf-8")
    if args.fail_on_stable_regression and stable_regressions:
        raise SystemExit("Stable performance regressions detected: " + " | ".join(stable_regressions))


if __name__ == "__main__":
    main()
