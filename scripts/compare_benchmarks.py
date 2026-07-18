from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--baseline-doc", required=True)
    parser.add_argument("--after-doc", required=True)
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
        "| Scenario | Points | Workers | Duplicate ratio | Cache | "
        "Throughput (points/s) | P95 (s) | RSS delta |",
        "|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for item in baseline["measurements"]:
        baseline_lines.append(
            "| {scenario} | {points} | {workers} | {duplicate_ratio:.0%} | {cache_mode} | "
            "{throughput_points_s:.3f} | {p95_point_s:.6f} | {rss_delta} |".format(**item)
        )

    after_lines = [
        "# Portable performance after AspenOps v2 changes",
        "",
        "Candidate revision: `agent/aspenops-v2-reliability-performance`.",
        "",
        after["boundary"],
        "",
        "| Scenario | Points | Workers | Duplicate ratio | Cache | Throughput | "
        "Throughput change | P95 change | Regression |",
        "|---|---:|---:|---:|---|---:|---:|---:|---|",
    ]
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
        after_lines.append(
            f"| {candidate['scenario']} | {candidate['points']} | {candidate['workers']} | "
            f"{candidate['duplicate_ratio']:.0%} | {candidate['cache_mode']} | "
            f"{candidate['throughput_points_s']:.3f} | {format_change(throughput_change)} | "
            f"{format_change(p95_change)} | {regression_label(throughput_change, p95_change)} |"
        )

    after_lines.extend(
        [
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


if __name__ == "__main__":
    main()
