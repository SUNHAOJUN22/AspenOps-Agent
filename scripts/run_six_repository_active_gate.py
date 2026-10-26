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
import platform
import re
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
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"cannot resolve remote main for {repository}: {completed.stderr.strip()}"
        )
    fields = completed.stdout.strip().split()
    if len(fields) != 2 or fields[1] != "refs/heads/main":
        raise RuntimeError(
            f"unexpected ls-remote response for {repository!r}: {completed.stdout!r}"
        )
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


def local_source_identity(tested_sha: str) -> dict[str, str]:
    """Check the actual checkout used by commands, including staged/untracked work.

    These are Git-state checkpoints, not an immutable filesystem or dependency
    sandbox. Runtime artifacts must be ignored by Git or outside the checkout.
    """
    cwd = Path.cwd().resolve()

    def git(*arguments: str) -> str:
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(cwd), *arguments],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"local Git identity check failed: {result.stderr.strip()}")
        return result.stdout.strip()

    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    if cwd != root:
        raise RuntimeError(f"formal commands must run from repository root: {cwd} != {root}")
    head = git("rev-parse", "--verify", "HEAD")
    if head != tested_sha:
        raise RuntimeError(f"local HEAD mismatch: tested={tested_sha} local={head}")
    index_entries = git("ls-files", "-v", "-z").split("\0")
    if any(entry and (entry[0].islower() or entry[0] == "S") for entry in index_entries):
        raise RuntimeError("local source uses assume-unchanged or skip-worktree index flags")
    status = git("status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none")
    if status:
        raise RuntimeError(f"local source is not clean: {status}")
    return {"repository_root": str(root), "head": head, "tree": git("rev-parse", "HEAD^{tree}")}


def read_previous(
    path: Path,
    tested_sha: str,
    *,
    expected_context: dict[str, Any],
    next_stage: int,
    source_tree: str,
) -> tuple[int, int]:
    """Continue only a matching, internally consistent v5 stage receipt.

    The caller must trust the prior local receipt; hashes and field consistency
    do not authenticate its author or independently prove the recorded runtime.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("previous stage must be a JSON object")
    if payload.get("verdict") != "PASS":
        raise RuntimeError(f"previous stage is not PASS: {payload.get('verdict')!r}")
    if payload.get("tested_sha") != tested_sha:
        raise RuntimeError(
            "previous stage SHA mismatch: "
            f"expected {tested_sha}, observed {payload.get('tested_sha')!r}"
        )
    if payload.get("schema_version") != "six-repository-active-gate/v5":
        raise RuntimeError("previous stage lacks v5 local-source and command identity")
    for key in ("repository", "kind", "slug", "command_identity", "commands"):
        if payload.get(key) != expected_context[key]:
            raise RuntimeError(f"previous stage {key} mismatch")
    source_identity = payload.get("source_identity")
    if not isinstance(source_identity, dict) or (
        source_identity.get("head"),
        source_identity.get("tree"),
    ) != (tested_sha, source_tree):
        raise RuntimeError("previous stage local-source identity mismatch")
    for key in (
        "stage",
        "target_active_ns",
        "initial_active_ns",
        "initial_cycles",
        "stage_active_ns",
        "stage_cycles",
        "total_active_ns",
        "total_cycles",
    ):
        if type(payload.get(key)) is not int or payload[key] < 0:
            raise RuntimeError(f"previous stage {key} must be a nonnegative integer")
    if payload["stage"] != next_stage - 1 or payload["stage"] < 1:
        raise RuntimeError("previous stage is not the immediately preceding stage")
    if (
        payload.get("failure") is not None
        or payload["stage_active_ns"] == 0
        or payload["stage_cycles"] == 0
        or payload["total_active_ns"] != payload["initial_active_ns"] + payload["stage_active_ns"]
        or payload["total_cycles"] != payload["initial_cycles"] + payload["stage_cycles"]
        or not payload["initial_active_ns"]
        < payload["target_active_ns"]
        <= payload["total_active_ns"]
        or (payload["stage"] == 1 and (payload["initial_active_ns"] or payload["initial_cycles"]))
        or (
            payload["stage"] > 1
            and (not payload["initial_active_ns"] or not payload["initial_cycles"])
        )
    ):
        raise RuntimeError("previous stage totals do not describe a completed formal stage")
    return payload["total_active_ns"], payload["total_cycles"]


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
    """Run one stage bound to remote main, the local checkout and its commands."""
    if args.stage <= 0:
        raise ValueError("stage must be positive")
    if args.target_active_ns <= 0:
        raise ValueError("target-active-ns must be positive")
    if (
        not isinstance(args.tested_sha, str)
        or re.fullmatch(r"[0-9a-f]{40}", args.tested_sha) is None
    ):
        raise ValueError("tested-sha must be a complete lowercase SHA-1 commit identity")

    commands = COMMANDS[args.kind]
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / f"{args.slug}-stage-{args.stage}.ndjson"
    summary_path = output_dir / f"{args.slug}-summary.json"

    initial_active_ns = 0
    initial_cycles = 0
    summary: dict[str, Any] = {
        "schema_version": "six-repository-active-gate/v5",
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

    stage_active_ns = 0
    stage_cycles = 0

    def check_local_source(where: str) -> bool:
        try:
            observed = local_source_identity(args.tested_sha)
            previous = summary.get("source_identity")
            if previous is not None and observed != previous:
                raise RuntimeError("local checkout identity changed during the stage")
            summary["source_identity"] = observed
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            failure = f"SOURCE_MISMATCH {where}: {exc}"
            write_terminal_summary(
                summary_path,
                summary,
                verdict="SOURCE_MISMATCH",
                failure=failure,
                stage_active_ns=stage_active_ns,
                stage_cycles=stage_cycles,
            )
            print(failure, file=sys.stderr)
            return False
        return True

    current_remote = remote_main_sha(args.repository)
    if current_remote != args.tested_sha:
        failure = f"STALE_MAIN before stage: tested={args.tested_sha} remote={current_remote}"
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

    if not check_local_source("before stage"):
        return 3

    try:
        if args.previous_summary is not None:
            initial_active_ns, initial_cycles = read_previous(
                args.previous_summary.resolve(),
                args.tested_sha,
                expected_context=summary,
                next_stage=args.stage,
                source_tree=summary["source_identity"]["tree"],
            )
        elif args.stage != 1:
            raise RuntimeError("stages after stage 1 require the immediately preceding receipt")
        if initial_active_ns >= args.target_active_ns:
            raise RuntimeError(
                "a later stage must advance the previous completed active-time total"
            )
    except (OSError, ValueError, RuntimeError) as exc:
        failure = f"INVALID_PREVIOUS_STAGE: {exc}"
        write_terminal_summary(
            summary_path,
            summary,
            verdict="INVALID_PREVIOUS_STAGE",
            failure=failure,
            stage_active_ns=0,
            stage_cycles=0,
        )
        print(failure, file=sys.stderr)
        return 2
    summary.update(initial_active_ns=initial_active_ns, initial_cycles=initial_cycles)

    with ledger_path.open("w", encoding="utf-8", newline="\n") as ledger:
        while initial_active_ns + stage_active_ns < args.target_active_ns:
            if not check_local_source(f"before cycle {stage_cycles + 1}"):
                return 3
            stage_cycles += 1
            cycle_started_at = utc_now()
            returncode, output, elapsed_ns = execute_cycle(commands)
            stage_active_ns += elapsed_ns
            record = {
                "schema_version": "six-repository-active-cycle/v5",
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
            if not check_local_source(f"after cycle {stage_cycles}"):
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
    if not check_local_source("at stage completion"):
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
