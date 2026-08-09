#!/usr/bin/env python3
"""Run an exact-SHA active-test stage and emit a machine-readable ledger.

Only time spent inside the configured repository test command contributes to
``stage_active_ns``. Dependency installation, remote-SHA checks, artifact I/O,
logging and retry backoff are deliberately excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

COMMANDS: dict[str, str] = {
    "aspenops": "uv run pytest -W error::ResourceWarning -q",
    "scicomputation": "python scripts/verify_all.py --profile core",
    "processing": (
        "python scripts/run_ci.py && "
        "python -m tsao.cli doctor --root . --profile core"
    ),
    "resindb": (
        "npm run validate:docs && "
        "npm run validate:source && "
        "npm run validate:data && "
        "npm run validate:compute && "
        "npm run validate:scientific-ui && "
        "npm run lint && "
        "npm run typecheck && "
        "npm run test:unit && "
        "npm run test:science && "
        "npm run build"
    ),
    "dft": "python scripts/quality_gate.py",
    "researcher": (
        "python scripts/final_acceptance_preflight.py --root . --json && "
        "python -m pytest -q -p hypothesis.extra.pytestplugin"
    ),
}


def utc_now() -> str:
    """Return a stable UTC timestamp."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_bytes(payload: bytes) -> str:
    """Hash command output without normalizing or decoding it."""
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically so an interrupted job cannot publish a partial summary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def remote_main_sha(repository: str) -> str:
    """Resolve a public repository's current main SHA with bounded retry."""
    url = f"https://github.com/{repository}.git"
    error: Exception | None = None
    for attempt in range(1, 4):
        try:
            result = subprocess.run(
                ["git", "ls-remote", url, "refs/heads/main"],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            fields = result.stdout.strip().split()
            if len(fields) != 2 or len(fields[0]) != 40:
                raise RuntimeError(
                    f"unexpected ls-remote response for {repository}: "
                    f"{result.stdout!r}"
                )
            return fields[0]
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            error = exc
            if attempt < 3:
                time.sleep(2 * attempt)
    raise RuntimeError(f"unable to resolve main for {repository}: {error}")


def read_previous(path: Path | None, tested_sha: str) -> tuple[int, int]:
    """Validate a previous stage before carrying its active time forward."""
    if path is None:
        return 0, 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("verdict") != "PASS":
        raise RuntimeError(f"previous stage is not PASS: {path}")
    if payload.get("tested_sha") != tested_sha:
        raise RuntimeError(
            "previous stage SHA mismatch: "
            f"{payload.get('tested_sha')} != {tested_sha}"
        )
    active_ns = payload.get("total_active_ns")
    cycles = payload.get("total_cycles")
    if isinstance(active_ns, bool) or not isinstance(active_ns, int) or active_ns < 0:
        raise RuntimeError("previous total_active_ns is invalid")
    if isinstance(cycles, bool) or not isinstance(cycles, int) or cycles < 0:
        raise RuntimeError("previous total_cycles is invalid")
    return active_ns, cycles


def base_summary(
    *,
    slug: str,
    kind: str,
    repository: str,
    tested_sha: str,
    stage: int,
    target_active_ns: int,
    previous_active_ns: int,
    previous_cycles: int,
    command: str,
    started_at: str,
) -> dict[str, Any]:
    """Build the common immutable identity fields for a stage summary."""
    return {
        "schema_version": "six-repository-active-stage-2.0.0",
        "slug": slug,
        "kind": kind,
        "repository": repository,
        "tested_sha": tested_sha,
        "stage": stage,
        "target_active_ns": target_active_ns,
        "previous_active_ns": previous_active_ns,
        "previous_cycles": previous_cycles,
        "stage_active_ns": 0,
        "stage_cycles": 0,
        "total_active_ns": previous_active_ns,
        "total_cycles": previous_cycles,
        "command": command,
        "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
        "started_at": started_at,
        "ended_at": None,
        "runner_os": platform.platform(),
        "python": platform.python_version(),
        "workflow_run_id": os.getenv("GITHUB_RUN_ID"),
        "workflow_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "job": os.getenv("GITHUB_JOB"),
        "verdict": "RUNNING",
        "failure": None,
    }


def write_terminal_summary(
    summary_path: Path,
    summary: dict[str, Any],
    *,
    verdict: str,
    failure: str | None,
    stage_active_ns: int,
    stage_cycles: int,
) -> None:
    """Finalize a stage summary without weakening an earlier failure."""
    summary.update(
        {
            "stage_active_ns": stage_active_ns,
            "stage_cycles": stage_cycles,
            "total_active_ns": summary["previous_active_ns"] + stage_active_ns,
            "total_cycles": summary["previous_cycles"] + stage_cycles,
            "ended_at": utc_now(),
            "verdict": verdict,
            "failure": failure,
        }
    )
    atomic_json(summary_path, summary)


def run_stage(args: argparse.Namespace) -> int:
    """Execute one active-test stage."""
    if args.kind not in COMMANDS:
        raise ValueError(f"unsupported repository kind: {args.kind}")
    if len(args.tested_sha) != 40:
        raise ValueError("tested SHA must contain exactly 40 hexadecimal characters")
    try:
        int(args.tested_sha, 16)
    except ValueError as exc:
        raise ValueError("tested SHA is not hexadecimal") from exc
    if args.target_active_ns <= 0:
        raise ValueError("target active time must be positive")
    if args.stage not in {1, 2}:
        raise ValueError("stage must be 1 or 2")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / f"{args.slug}-ledger.jsonl"
    summary_path = output_dir / f"{args.slug}-summary.json"
    last_log_path = output_dir / f"{args.slug}-last-cycle.log"
    previous_active_ns, previous_cycles = read_previous(
        args.previous_summary,
        args.tested_sha,
    )
    command = COMMANDS[args.kind]
    summary = base_summary(
        slug=args.slug,
        kind=args.kind,
        repository=args.repository,
        tested_sha=args.tested_sha,
        stage=args.stage,
        target_active_ns=args.target_active_ns,
        previous_active_ns=previous_active_ns,
        previous_cycles=previous_cycles,
        command=command,
        started_at=utc_now(),
    )
    atomic_json(summary_path, summary)

    initial_remote = remote_main_sha(args.repository)
    if initial_remote != args.tested_sha:
        failure = (
            f"STALE_MAIN before stage: tested={args.tested_sha} "
            f"remote={initial_remote}"
        )
        write_terminal_summary(
            summary_path,
            summary,
            verdict="STALE_MAIN",
            failure=failure,
            stage_active_ns=0,
            stage_cycles=0,
        )
        print(failure, file=sys.stderr)
        return 3

    stage_active_ns = 0
    stage_cycles = 0
    with ledger_path.open("a", encoding="utf-8", newline="\n") as ledger:
        while stage_active_ns < args.target_active_ns:
            stage_cycles += 1
            cycle_started_at = utc_now()
            started_ns = time.monotonic_ns()
            completed = subprocess.run(
                command,
                shell=True,
                executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            ended_ns = time.monotonic_ns()
            elapsed_ns = ended_ns - started_ns
            if elapsed_ns <= 0:
                raise RuntimeError("monotonic clock produced a non-positive duration")
            stage_active_ns += elapsed_ns
            last_log_path.write_bytes(completed.stdout)
            record = {
                "schema_version": "six-repository-active-cycle-2.0.0",
                "slug": args.slug,
                "repository": args.repository,
                "tested_sha": args.tested_sha,
                "stage": args.stage,
                "cycle": stage_cycles,
                "started_at": cycle_started_at,
                "ended_at": utc_now(),
                "elapsed_ns": elapsed_ns,
                "stage_active_ns": stage_active_ns,
                "returncode": completed.returncode,
                "output_bytes": len(completed.stdout),
                "output_sha256": sha256_bytes(completed.stdout),
            }
            ledger.write(json.dumps(record, sort_keys=True) + "\n")
            ledger.flush()
            print(
                json.dumps(
                    {
                        "slug": args.slug,
                        "stage": args.stage,
                        "cycle": stage_cycles,
                        "returncode": completed.returncode,
                        "elapsed_s": round(elapsed_ns / 1_000_000_000, 3),
                        "active_h": round(stage_active_ns / 3_600_000_000_000, 6),
                        "target_h": round(
                            args.target_active_ns / 3_600_000_000_000,
                            6,
                        ),
                        "output_sha256": record["output_sha256"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if completed.returncode != 0:
                failure_log = output_dir / (
                    f"{args.slug}-failure-stage-{args.stage}-"
                    f"cycle-{stage_cycles}.log"
                )
                failure_log.write_bytes(completed.stdout)
                failure = (
                    f"test command failed with return code {completed.returncode} "
                    f"at stage {args.stage} cycle {stage_cycles}"
                )
                write_terminal_summary(
                    summary_path,
                    summary,
                    verdict="FAIL",
                    failure=failure,
                    stage_active_ns=stage_active_ns,
                    stage_cycles=stage_cycles,
                )
                print(failure, file=sys.stderr)
                return 1

            current_remote = remote_main_sha(args.repository)
            if current_remote != args.tested_sha:
                failure = (
                    f"STALE_MAIN after cycle {stage_cycles}: "
                    f"tested={args.tested_sha} remote={current_remote}"
                )
                write_terminal_summary(
                    summary_path,
                    summary,
                    verdict="STALE_MAIN",
                    failure=failure,
                    stage_active_ns=stage_active_ns,
                    stage_cycles=stage_cycles,
                )
                print(failure, file=sys.stderr)
                return 3

    final_remote = remote_main_sha(args.repository)
    if final_remote != args.tested_sha:
        failure = (
            f"STALE_MAIN at stage completion: tested={args.tested_sha} "
            f"remote={final_remote}"
        )
        write_terminal_summary(
            summary_path,
            summary,
            verdict="STALE_MAIN",
            failure=failure,
            stage_active_ns=stage_active_ns,
            stage_cycles=stage_cycles,
        )
        print(failure, file=sys.stderr)
        return 3

    write_terminal_summary(
        summary_path,
        summary,
        verdict="PASS",
        failure=None,
        stage_active_ns=stage_active_ns,
        stage_cycles=stage_cycles,
    )
    print(summary_path.read_text(encoding="utf-8"), flush=True)
    return 0


def parse_args() -> argparse.Namespace:
    """Parse the active-stage command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--kind", required=True, choices=sorted(COMMANDS))
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tested-sha", required=True)
    parser.add_argument("--stage", required=True, type=int)
    parser.add_argument("--target-active-ns", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--previous-summary", type=Path)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    try:
        return run_stage(parse_args())
    except Exception as exc:  # noqa: BLE001 - terminal machine summary is required.
        print(f"active qualification runner error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
