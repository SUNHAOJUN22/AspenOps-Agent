from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

from . import __version__
from .batch import dry_run_document, run_batch_document, run_batch_file
from .benchmark import benchmark_worker_matrix
from .certification import certify_batch_document
from .config import Settings
from .doctor import diagnose
from .licensed_certification import (
    certification_preflight,
    execute_licensed_certification,
    load_licensed_plan,
    verify_licensed_certification_bundle,
)
from .optimization import run_optimization_document
from .policy import Policy
from .pool_manager import PoolManager
from .provenance import verify_run_bundle, write_run_bundle
from .scheduler import BackgroundScheduler


def _json_print(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str, allow_nan=False))


def _resource_path(name: str) -> Path:
    resource = files("aspenops_nexus.data").joinpath(name)
    with as_file(resource) as path:
        return Path(path)


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Request root must be a JSON object")
    return value


def _controlled_path(path: str | Path, settings: Any) -> Path:
    mode = str(getattr(settings, "mode", "default"))
    roots = tuple(Path(root) for root in getattr(settings, "allowed_roots", ()))
    return Policy(mode, roots).assert_path(path)


def _demo_request() -> dict[str, Any]:
    return {
        "backend": "mock",
        "model_path": str(_resource_path("mock-case.json")),
        "registry_path": str(_resource_path("node-registry.json")),
        "workers": 2,
        "reset_mode": "reinitialize",
        "timeout_s": 30,
        "base_writes": [
            {
                "key": "stream.input.pressure",
                "identifiers": {"stream": "FEED"},
                "value": 5,
                "unit": "bar",
            },
            {
                "key": "stream.input.mass_flow",
                "identifiers": {"stream": "FEED"},
                "value": 120,
                "unit": "kg/h",
            },
            {
                "key": "block.input.stages",
                "identifiers": {"block": "COL1"},
                "value": 28,
                "unit": "1",
            },
        ],
        "points": [
            {
                "writes": [
                    {
                        "key": "stream.input.temperature",
                        "identifiers": {"stream": "FEED"},
                        "value": temperature,
                        "unit": "C",
                    },
                    {
                        "key": "block.input.reflux_ratio",
                        "identifiers": {"block": "COL1"},
                        "value": reflux,
                        "unit": "1",
                    },
                ]
            }
            for temperature, reflux in [(70, 1.8), (90, 2.4), (110, 3.0)]
        ],
        "reads": [
            {
                "key": "stream.output.purity",
                "identifiers": {"stream": "PRODUCT"},
                "unit": "fraction",
            },
            {
                "key": "block.output.reboiler_duty",
                "identifiers": {"block": "COL1"},
                "unit": "kW",
            },
            {
                "key": "reactor.output.conversion",
                "identifiers": {"block": "R1"},
                "unit": "fraction",
            },
        ],
    }


def command_demo(args: argparse.Namespace) -> int:
    del args
    results = run_batch_document(_demo_request(), Settings.from_env())
    _json_print({"version": __version__, "results": results})
    return 0 if all(result["ok"] for result in results) else 2


def command_doctor(args: argparse.Namespace) -> int:
    result = diagnose(Settings.from_env(), probe=args.probe)
    _json_print(result)
    return 0 if result["ready"] else 2


def command_dry_run(args: argparse.Namespace) -> int:
    _json_print(dry_run_document(_load(args.request), Settings.from_env()))
    return 0


def command_run_batch(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    request_path = Path(args.request).resolve()
    request = _load(request_path)
    results = run_batch_file(request_path, settings)
    output = _controlled_path(
        args.output or settings.state_dir / "latest-results.json",
        settings,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    bundle_path = _controlled_path(
        args.bundle or settings.state_dir / "latest-run-bundle.zip",
        settings,
    )
    write_run_bundle(request=request, results=results, output_path=bundle_path)
    _json_print(
        {
            "results_path": str(output),
            "bundle_path": str(bundle_path),
            "results": results,
        }
    )
    return 0 if all(result["ok"] for result in results) else 2


def command_submit(args: argparse.Namespace) -> int:
    scheduler = BackgroundScheduler(Settings.from_env())
    job_id = scheduler.submit(_load(args.request))
    _json_print({"job_id": job_id, "state_db": str(scheduler.store.path)})
    return 0


def command_job(args: argparse.Namespace) -> int:
    store = BackgroundScheduler(Settings.from_env()).store
    record = store.get(args.job_id)
    _json_print({"found": record is not None, "job": record})
    return 0 if record is not None else 2


def command_benchmark(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    candidates = [int(x) for x in args.workers.split(",")]
    result = benchmark_worker_matrix(
        model_path=Path(args.model).resolve(),
        registry_path=Path(args.registry).resolve(),
        points=args.points,
        worker_candidates=candidates,
        state_dir=settings.state_dir,
    )
    _json_print(result)
    return 0


def command_optimize(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    document = _load(args.request)
    with PoolManager(
        cache_path=settings.state_dir / "cache.sqlite3",
        license_slots=settings.license_slots,
        max_resident_cases=settings.max_resident_cases,
        idle_timeout_s=settings.pool_idle_timeout_s,
        worker_max_points=settings.worker_max_points,
        worker_max_age_s=settings.worker_max_age_s,
        startup_timeout_s=settings.startup_timeout_s,
        cache_failures=settings.cache_failures,
    ) as pool_manager:
        result = run_optimization_document(
            document,
            settings,
            pool_manager=pool_manager,
        )
    output = _controlled_path(args.output, settings)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    _json_print({"result_path": str(output), "result": result})
    return 0 if result["status"] == "completed" else 2


def command_certify(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    document = _load(args.request)
    kwargs: dict[str, Any] = {
        "repeats": args.repeats,
        "abs_tol": args.abs_tol,
        "rel_tol": args.rel_tol,
    }
    if hasattr(args, "workers"):
        kwargs["workers"] = args.workers
    if hasattr(args, "engineering_approved"):
        kwargs["engineering_approved"] = args.engineering_approved
    report = certify_batch_document(document, settings, **kwargs)
    output = _controlled_path(args.output, settings)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    _json_print({"report_path": str(output), "passed": report["passed"]})
    return 0 if report["passed"] else 2


def command_certification_preflight(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    plan = load_licensed_plan(args.plan)
    report = certification_preflight(plan, settings)
    output = _controlled_path(
        args.output or settings.state_dir / "licensed-certification" / "preflight.json",
        settings,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    _json_print({**report, "preflight_path": str(output)})
    return 0 if report.get("ready") else 2


def command_certify_licensed(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    plan = load_licensed_plan(args.plan)
    output_dir = _controlled_path(
        args.output_dir or settings.state_dir / "licensed-certification",
        settings,
    )
    report = execute_licensed_certification(
        plan,
        settings,
        output_dir=output_dir,
    )
    _json_print(report)
    verification = report.get("bundle_verification", {})
    bundle_ok = isinstance(verification, dict) and bool(verification.get("ok"))
    return 0 if report.get("runtime_gate_passed") and bundle_ok else 2


def command_verify_licensed_bundle(args: argparse.Namespace) -> int:
    report = verify_licensed_certification_bundle(
        args.bundle,
        trusted_public_key=args.public_key,
    )
    _json_print(report)
    return 0 if report.get("ok") else 2


def command_verify_bundle(args: argparse.Namespace) -> int:
    result = verify_run_bundle(args.bundle)
    _json_print(result)
    return 0 if result["ok"] else 2


def command_mcp(args: argparse.Namespace) -> int:
    del args
    from .mcp_server import main as mcp_main

    mcp_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aspenops",
        description="AspenOps 2.0 deterministic execution fabric for Aspen automation",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Run the portable nonlinear Mock end-to-end example")
    demo.set_defaults(func=command_demo)

    doctor = sub.add_parser("doctor", help="Inspect host, policy and registered COM candidates")
    doctor.add_argument("--probe", action="store_true")
    doctor.set_defaults(func=command_doctor)

    dry_run = sub.add_parser("dry-run", help="Validate a request without opening Aspen")
    dry_run.add_argument("request")
    dry_run.set_defaults(func=command_dry_run)

    run_batch = sub.add_parser("run-batch", help="Execute a batch and write an evidence bundle")
    run_batch.add_argument("request")
    run_batch.add_argument("--output")
    run_batch.add_argument("--bundle")
    run_batch.set_defaults(func=command_run_batch)

    submit = sub.add_parser("submit", help="Submit a durable background job")
    submit.add_argument("request")
    submit.set_defaults(func=command_submit)

    job = sub.add_parser("job", help="Read durable job status")
    job.add_argument("job_id")
    job.set_defaults(func=command_job)

    benchmark = sub.add_parser("benchmark", help="Benchmark the portable scheduler")
    benchmark.add_argument("--points", type=int, default=24)
    benchmark.add_argument("--workers", default="1,2,4")
    benchmark.add_argument("--model", default=str(_resource_path("mock-case.json")))
    benchmark.add_argument("--registry", default=str(_resource_path("node-registry.json")))
    benchmark.set_defaults(func=command_benchmark)

    optimize = sub.add_parser("optimize", help="Run a budgeted batch constrained optimization")
    optimize.add_argument("request")
    optimize.add_argument("--output", default="var/optimization-result.json")
    optimize.set_defaults(func=command_optimize)

    certify = sub.add_parser(
        "certify",
        help="Run a scoped repeatability gate; never grants real Aspen certification",
    )
    certify.add_argument("request")
    certify.add_argument("--output", default="var/certification-report.json")
    certify.add_argument("--repeats", type=int, default=3)
    certify.add_argument("--abs-tol", type=float, default=1e-8)
    certify.add_argument("--rel-tol", type=float, default=1e-6)
    certify.add_argument("--workers", type=int, default=1)
    certify.add_argument("--engineering-approved", action="store_true")
    certify.set_defaults(func=command_certify)

    preflight = sub.add_parser(
        "certification-preflight",
        help="Validate a licensed certification plan without opening COM",
    )
    preflight.add_argument("plan")
    preflight.add_argument("--output")
    preflight.set_defaults(func=command_certification_preflight)

    licensed = sub.add_parser(
        "certify-licensed",
        help="Execute an approved licensed plan and create a signed pending-review bundle",
    )
    licensed.add_argument("plan")
    licensed.add_argument("--output-dir")
    licensed.set_defaults(func=command_certify_licensed)

    licensed_verify = sub.add_parser(
        "verify-licensed-bundle",
        help="Verify a signed licensed certification bundle with a trusted public key",
    )
    licensed_verify.add_argument("bundle")
    licensed_verify.add_argument("--public-key", required=True)
    licensed_verify.set_defaults(func=command_verify_licensed_bundle)

    verify = sub.add_parser("verify-bundle", help="Verify evidence-bundle hashes")
    verify.add_argument("bundle")
    verify.set_defaults(func=command_verify_bundle)

    mcp = sub.add_parser("mcp", help="Run the local stdio MCP server")
    mcp.set_defaults(func=command_mcp)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = int(args.func(args))
    except KeyboardInterrupt:
        code = 130
    except Exception as exc:
        _json_print({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main(sys.argv[1:])
