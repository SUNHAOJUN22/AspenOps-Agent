from __future__ import annotations

import argparse
import random
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


class OrderGateError(RuntimeError):
    """Raised when the test-order qualification gate cannot run safely."""


def _collect_node_ids(pytest_args: Sequence[str]) -> list[str]:
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q", *pytest_args]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise OrderGateError(
            f"pytest collection failed:\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )

    node_ids = [line.strip() for line in completed.stdout.splitlines() if "::" in line]
    if not node_ids:
        raise OrderGateError("pytest collection produced no test node IDs")
    if len(node_ids) != len(set(node_ids)):
        raise OrderGateError("pytest collection produced duplicate test node IDs")
    return node_ids


def _reverse_order(node_ids: Sequence[str]) -> list[str]:
    return list(reversed(node_ids))


def _random_order(node_ids: Sequence[str], seed: int) -> list[str]:
    ordered = list(node_ids)
    random.Random(seed).shuffle(ordered)
    return ordered


def _run_order(
    *,
    label: str,
    node_ids: Sequence[str],
    output_dir: Path,
    pytest_args: Sequence[str],
) -> None:
    order_path = output_dir / f"test-order-{label}.txt"
    junit_path = output_dir / f"junit-order-{label}.xml"
    log_path = output_dir / f"pytest-order-{label}.log"
    order_path.write_text("\n".join(node_ids) + "\n", encoding="utf-8")

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-W",
        "error::ResourceWarning",
        f"--junitxml={junit_path}",
        *pytest_args,
        *node_ids,
    ]
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        completed = subprocess.run(
            command,
            check=False,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    if completed.returncode != 0:
        raise OrderGateError(
            f"{label} test-order run failed with exit code {completed.returncode}; see {log_path}"
        )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the complete pytest suite in reverse and deterministic random order."
    )
    parser.add_argument("--seed", type=int, default=20260728)
    parser.add_argument("--output-dir", type=Path, default=Path("var/ci"))
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional pytest arguments after --.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    pytest_args = list(args.pytest_args)
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    node_ids = _collect_node_ids(pytest_args)

    _run_order(
        label="reverse",
        node_ids=_reverse_order(node_ids),
        output_dir=output_dir,
        pytest_args=pytest_args,
    )
    _run_order(
        label=f"random-{args.seed}",
        node_ids=_random_order(node_ids, args.seed),
        output_dir=output_dir,
        pytest_args=pytest_args,
    )
    print(
        f"Order-independence gate passed for {len(node_ids)} tests (reverse and seed={args.seed})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
