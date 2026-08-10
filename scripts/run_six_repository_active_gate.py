#!/usr/bin/env python3
"""Run an exact-SHA active-test stage and emit a machine-readable ledger.

Only monotonic time spent inside configured formal test subprocesses contributes
to ``stage_active_ns``. Dependency installation, remote-SHA checks, artifact I/O,
ledger writes, logging and retry backoff are deliberately excluded.
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

Command = tuple[str, ...]
CommandGroup = tuple[Command, ...]

COMMANDS: dict[str, CommandGroup] = {
    "aspenops": (
        ("uv", "run", "ruff", "check", "."),
        ("uv", "run", "ruff", "format", "--check", "."),
        ("uv", "run", "mypy", "src"),
        ("uv", "run", "python", "-m", "compileall", "-q", "src", "scripts"),
        ("uv", "run", "pytest", "-q", "-W", "error::ResourceWarning"),
        ("uv", "run", "aspenops", "demo"),
        ("uv", "run", "python", "scripts/check_mcp.py"),
        ("git", "diff", "--exit-code"),
    ),
    "scicomputation": (("python", "scripts/verify_all.py", "--profile", "core"),),
    "processing": (
        ("python", "scripts/run_ci.py"),
        ("python", "-m", "tsao.cli", "doctor", "--root", ".", "--profile", "core"),
    ),
    "resindb": (
        ("npm", "run", "validate:docs"),
        ("npm", "run", "validate:source"),
        ("npm", "run", "validate:data"),
        ("npm", "run", "validate:compute"),
        ("npm", "run", "validate:scientific-ui"),
        ("npm", "run", "lint"),
        ("npm", "run", "typecheck"),
        ("npm", "run", "test:unit"),
        ("npm", "run", "test:science"),
        ("npm", "run", "build"),
    ),
    "dft": (("python", "scripts/quality_gate.py"),),
    "researcher": (
        (
            "python",
            "scripts/final_acceptance_preflight.py",
            "--root",
            ".",
            "--json",
        ),
        ("python", "-m", "pytest", "-q", "-p", "hypothesis.extra.pytestplugin"),
    ),
}


def utc_now() -> str:
    """Return a stable UTC timestamp."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_bytes(payload: bytes) -> str:
    """Hash command output without normalizing or decoding it."""
    return hashlib.sha256(payload).hexdigest()


def command_identity(commands: CommandGroup) -> str:
    """Return a deterministic hash for the exact argument-vector sequence."""
    payload = json.dumps(
        [list(command) for command in commands],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically so interruption cannot publish a partial summary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def remote_main_sha(repository: str) -> str:
    """Read the current remote ``main`` without mutating the local repository."""
    completed = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{repository}.git", "refs/heads/main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"cannot resolve remote main for {repository}: {completed.stderr.strip()}"
        )
    fields = completed.stdout.strip().split()
    if len(fields) != 2 or fields[1] != "refs/heads/main":
        raise RuntimeError(f"unexpected ls-remote response for {repository!r}: {completed.stdout!r}")
    return fields[0]


def execute_cycle(commands: CommandGroup) -> tuple[int, bytes, int]:
    """Execute one formal cycle, stopping at the first failed command.

    The returned nanoseconds cover formal command subprocesses only. No setup,
    remote-SHA check, sleep, ledger I/O or artifact work is included.
    """
    output = bytearray()
    active_ns = 0
    for command in commands:
        started_ns = time.monotonic_ns()
        completed = subprocess.run(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        active_ns += time.monotonic_ns() - started_ns
        output.extend(b"$ ")
        output.extend(" ".join(command).encode("utf-8"))
        output.extend(b"\n")
        output.extend(completed.stdout)
        if not completed.stdout.endswith(b"\n"):
            output.extend(b"\n")
        if completed.returncode != 0:
            return completed.returncode, bytes(output), active_ns
    return 0, bytes(output), active_ns


def read_previous(path: Path, tested_sha: str) -> tuple[int, int]:
    """Load a prior stage only when its immutable identity is exactly aligned."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("verdict") != "PASS":
        raise RuntimeError(f"previous stage is not PASS: {payload.get('verdict')!r}")
    if payload.get("tested_sha") != tested_sha:
        raise RuntimeError(
            "previous stage SHA mismatch: "
            f"expected {tested_sha}, observed {payload.get('tested_sha')!r}"
        )
    return int(payload["total_active_ns"]), int(payload["total_cycles"])


def terminal_payload(
    base: dict[str, Any],
    *,
    verdict: str,
    failure: str | None,
    stage_active_ns: int,
    stage_cycles: int,
) -> dict[str, Any]:
    """Build one terminal summary without mutating the caller's base mapping."""
    payload = dict(base)
    payload.update(
        {
            "verdict": verdict,
            "failure": failure,
            "stage_active_ns": stage_active_ns,
            "stage_cycles": stage_cycles,
            "total_active_ns": int(base["initial_active_ns"]) + stage_active_ns,
            "total_cycles": int(base["initial_cycles"]) + stage_cycles,
            "ended_at": utc_now(),
        }
    )
    return payload


def write_terminal_summary(
    path: Path,
    base: dict[str, Any],
    *,
    verdict: str,
    failure: str | None,
    stage_active_ns: int,
    stage_cycles: int,
) -> None:
    """Persist the terminal state in one atomic write."""
    atomic_json(
        path,
        terminal_payload(
            base,
            verdict=verdict,
            failure=failure,
            stage_active_ns=stage_active_ns,
            stage_cycles=stage_cycles,
        ),
    )


def run_stage(args: argparse.Namespace) -> int:
    """Run one stage and fail closed on a moved remote ``main``."""
    if args.stage <= 0:
        raise ValueError("stage must be positive")
    if args.target_active_ns <= 0:
        raise ValueError("target-active-ns must be positive")
    if not args.tested_sha.strip():
        raise ValueError("tested-sha must not be empty")

    commands = COMMANDS[args.kind]
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / f"{args.slug}-stage-{args.stage}.ndjson"
    summary_path = output_dir / f"{args.slug}-summary.json"

    initial_active_ns = 0
    initial_cycles = 0
    if args.previous_summary is not None:
        initial_active_ns, initial_cycles = read_previous(
            args.previous_summary.resolve(),
            args.tested_sha,
        )
    if initial_active_ns >= args.target_active_ns:
        raise ValueError(
            "previous active time already meets/exceeds requested target; "
            "a later stage must advance the target"
        )

    summary: dict[str, Any] = {
        "schema_version": "six-repository-active-gate/v4",
        "slug": args.slug,
        "kind": args.kind,
        "repository": args.repository,
        "tested_sha": args.tested_sha,
        "stage": args.stage,
        "target_active_ns": args.target_active_ns,
        "initial_active_ns": initial_active_ns,
        "initial_cycles": initial_cycles,
        "command_identity": command_identity(commands),
        "commands": [list(command) for command in commands],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "started_at": utc_now(),
    }

    current_remote = remote_main_sha(args.repository)
    if current_remote != args.tested_sha:
        failure = (
            f"STALE_MAIN before stage: tested={args.tested_sha} remote={current_remote}"
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
    with ledger_path.open("w", encoding="utf-8", newline="\n") as ledger:
        while initial_active_ns + stage_active_ns < args.target_active_ns:
            stage_cycles += 1
            cycle_started_at = utc_now()
            returncode, output, elapsed_ns = execute_cycle(commands)
            stage_active_ns += elapsed_ns
            record = {
                "schema_version": "six-repository-active-cycle/v4",
                "slug": args.slug,
                "stage": args.stage,
                "cycle": stage_cycles,
                "started_at": cycle_started_at,
                "ended_at": utc_now(),
                "elapsed_ns": elapsed_ns,
                "stage_active_ns": stage_active_ns,
                "returncode": returncode,
                "output_bytes": len(output),
                "output_sha256": sha256_bytes(output),
            }
            ledger.write(json.dumps(record, sort_keys=True) + "\n")
            ledger.flush()
            print(
                json.dumps(
                    {
                        "slug": args.slug,
                        "stage": args.stage,
                        "cycle": stage_cycles,
                        "returncode": returncode,
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
            if returncode != 0:
                failure_log = output_dir / (
                    f"{args.slug}-failure-stage-{args.stage}-cycle-{stage_cycles}.log"
                )
                failure_log.write_bytes(output)
                failure = (
                    f"test command failed with return code {returncode} "
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
        failure = f"STALE_MAIN at stage completion: tested={args.tested_sha} remote={final_remote}"
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
