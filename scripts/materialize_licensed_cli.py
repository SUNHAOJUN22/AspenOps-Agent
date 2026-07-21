from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected CLI marker missing: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    path = Path("src/aspenops_nexus/cli.py")
    replace_once(
        path,
        "from .doctor import diagnose\n",
        '''from .doctor import diagnose
from .licensed_certification import (
    certification_preflight,
    execute_licensed_certification,
    load_licensed_plan,
    verify_licensed_certification_bundle,
)
''',
    )
    replace_once(
        path,
        '''    report = certify_batch_document(
        _load(args.request),
        Settings.from_env(),
        repeats=args.repeats,
        abs_tol=args.abs_tol,
        rel_tol=args.rel_tol,
    )
''',
        '''    kwargs: dict[str, Any] = {
        "repeats": args.repeats,
        "abs_tol": args.abs_tol,
        "rel_tol": args.rel_tol,
    }
    if hasattr(args, "workers"):
        kwargs["workers"] = args.workers
    if hasattr(args, "engineering_approved"):
        kwargs["engineering_approved"] = args.engineering_approved
    report = certify_batch_document(
        _load(args.request),
        Settings.from_env(),
        **kwargs,
    )
''',
    )
    replace_once(
        path,
        '''def command_verify_bundle(args: argparse.Namespace) -> int:
    result = verify_run_bundle(args.bundle)
    _json_print(result)
    return 0 if result["ok"] else 2
''',
        '''def command_certification_preflight(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    plan = load_licensed_plan(args.plan)
    report = certification_preflight(plan, settings)
    output = Path(
        args.output or settings.state_dir / "licensed-certification" / "preflight.json"
    ).resolve()
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
    output_dir = Path(
        args.output_dir or settings.state_dir / "licensed-certification"
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
''',
    )
    replace_once(
        path,
        '''    certify = sub.add_parser("certify", help="Repeat from independent model copies")
    certify.add_argument("request")
    certify.add_argument("--output", default="var/certification-report.json")
    certify.add_argument("--repeats", type=int, default=3)
    certify.add_argument("--abs-tol", type=float, default=1e-8)
    certify.add_argument("--rel-tol", type=float, default=1e-6)
    certify.set_defaults(func=command_certify)

    verify = sub.add_parser("verify-bundle", help="Verify evidence-bundle hashes")
''',
        '''    certify = sub.add_parser(
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
''',
    )


if __name__ == "__main__":
    main()
