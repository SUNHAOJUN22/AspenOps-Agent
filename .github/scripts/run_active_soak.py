#!/usr/bin/env python3
"""Run complete qualification cycles until a monotonic active-time target is met."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle-script", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--initial-ns", type=int, required=True)
    parser.add_argument("--target-ns", type=int, required=True)
    parser.add_argument("--stage", type=int, required=True)
    parser.add_argument("--tested-sha", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.initial_ns < 0 or args.target_ns <= args.initial_ns:
        raise SystemExit("invalid active-time interval")
    if not args.tested_sha.strip():
        raise SystemExit("tested SHA is empty")

    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.evidence_dir / f"stage-{args.stage}.ndjson"
    ledger.write_text("", encoding="utf-8")
    active_ns = args.initial_ns
    cycles = 0

    while active_ns < args.target_ns:
        cycles += 1
        started_epoch = int(time.time())
        started_active = time.monotonic_ns()
        log = args.evidence_dir / f"stage-{args.stage}-current.log"
        with log.open("w", encoding="utf-8") as stream:
            completed = subprocess.run(
                ["bash", str(args.cycle_script)],
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        cycle_active_ns = time.monotonic_ns() - started_active
        active_ns += cycle_active_ns
        row = {
            "stage": args.stage,
            "cycle": cycles,
            "tested_sha": args.tested_sha,
            "started_epoch": started_epoch,
            "ended_epoch": int(time.time()),
            "cycle_active_ns": cycle_active_ns,
            "cumulative_active_ns": active_ns,
            "target_active_ns": args.target_ns,
            "returncode": completed.returncode,
        }
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        if completed.returncode != 0:
            print(log.read_text(encoding="utf-8", errors="replace")[-30000:])
            raise SystemExit(
                f"stage {args.stage} cycle {cycles} failed with "
                f"{completed.returncode}"
            )
        print(
            f"stage={args.stage} cycle={cycles} PASS "
            f"active={active_ns / 3_600_000_000_000:.6f} h",
            flush=True,
        )

    summary = {
        "schema": "SUNHJ-SIX-HOUR-ACTIVE-QUALIFICATION-1",
        "stage": args.stage,
        "pass": True,
        "tested_sha": args.tested_sha,
        "stage_cycles": cycles,
        "cumulative_active_ns": active_ns,
        "cumulative_active_hours": active_ns / 3_600_000_000_000,
        "required_active_ns": args.target_ns,
        "duration_basis": "MONOTONIC_ACTIVE_TEST_EXECUTION_ONLY",
    }
    (args.evidence_dir / f"stage-{args.stage}-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"active_ns={active_ns}\n")
            stream.write(f"cycles={cycles}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
