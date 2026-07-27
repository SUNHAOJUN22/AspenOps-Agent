from __future__ import annotations

import argparse
import sys
from importlib.resources import as_file, files
from pathlib import Path

from . import __version__


def _resource_path(name: str) -> Path:
    resource = files("aspenops_nexus.data").joinpath(name)
    with as_file(resource) as path:
        return Path(path)


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI surface without importing the execution control plane."""

    parser = argparse.ArgumentParser(
        prog="aspenops",
        description="AspenOps 2.0 deterministic execution fabric for Aspen automation",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("demo", help="Run the portable nonlinear Mock end-to-end example")

    doctor = sub.add_parser("doctor", help="Inspect host, policy and registered COM candidates")
    doctor.add_argument("--probe", action="store_true")

    dry_run = sub.add_parser("dry-run", help="Validate a request without opening Aspen")
    dry_run.add_argument("request")

    run_batch = sub.add_parser("run-batch", help="Execute a batch and write an evidence bundle")
    run_batch.add_argument("request")
    run_batch.add_argument("--output")
    run_batch.add_argument("--bundle")

    submit = sub.add_parser("submit", help="Validate and enqueue a durable background job")
    submit.add_argument("request")

    job = sub.add_parser("job", help="Read durable job status")
    job.add_argument("job_id")

    cancel = sub.add_parser("cancel", help="Request durable job cancellation")
    cancel.add_argument("job_id")
    cancel.add_argument("--grace-s", type=float, default=2.0)

    scheduler_service = sub.add_parser(
        "scheduler",
        help="Run the durable scheduler service until interrupted",
    )
    scheduler_service.add_argument("--idle-wait-s", type=float, default=1.0)

    benchmark = sub.add_parser("benchmark", help="Benchmark the portable scheduler")
    benchmark.add_argument("--points", type=int, default=24)
    benchmark.add_argument("--workers", default="1,2,4")
    benchmark.add_argument("--model", default=str(_resource_path("mock-case.json")))
    benchmark.add_argument("--registry", default=str(_resource_path("node-registry.json")))

    optimize = sub.add_parser("optimize", help="Run a budgeted batch constrained optimization")
    optimize.add_argument("request")
    optimize.add_argument("--output")

    certify = sub.add_parser(
        "certify",
        help="Run a scoped repeatability gate; never grants real Aspen certification",
    )
    certify.add_argument("request")
    certify.add_argument("--output")
    certify.add_argument("--repeats", type=int, default=3)
    certify.add_argument("--abs-tol", type=float, default=1e-8)
    certify.add_argument("--rel-tol", type=float, default=1e-6)
    certify.add_argument("--workers", type=int, default=1)
    certify.add_argument("--engineering-approved", action="store_true")

    preflight = sub.add_parser(
        "certification-preflight",
        help="Validate a licensed certification plan without opening COM",
    )
    preflight.add_argument("plan")
    preflight.add_argument("--output")

    licensed = sub.add_parser(
        "certify-licensed",
        help="Execute an approved licensed plan and create a signed pending-review bundle",
    )
    licensed.add_argument("plan")
    licensed.add_argument("--output-dir")

    licensed_verify = sub.add_parser(
        "verify-licensed-bundle",
        help="Verify a signed licensed certification bundle with a trusted public key",
    )
    licensed_verify.add_argument("bundle")
    licensed_verify.add_argument("--public-key", required=True)

    verify = sub.add_parser("verify-bundle", help="Verify evidence-bundle hashes")
    verify.add_argument("bundle")

    sub.add_parser("mcp", help="Run the local stdio MCP server")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Handle help/version cheaply, then delegate real execution to the full CLI."""

    arguments = sys.argv[1:] if argv is None else argv
    build_parser().parse_args(arguments)

    from .cli import main as full_main

    full_main(arguments)


if __name__ == "__main__":
    main()
