from __future__ import annotations

import argparse
import json
import math
import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION = "docs/ACCEPTANCE_HARDENING_QUALIFICATION.json"
AUTHORITATIVE_WORKFLOWS = {
    "ci.yml",
    "generate-performance-evidence.yml",
    "licensed-aspen-certification.yml",
    "windows-control-plane.yml",
}
GOVERNED_VISUAL_ASSETS = {
    "adapter-conformance.svg",
    "agent-pipeline.svg",
    "backend-capabilities.svg",
    "cache-singleflight.svg",
    "cli-mcp-workflow.svg",
    "cold-warm-startup.svg",
    "com-isolation.svg",
    "durable-path-portability.svg",
    "evidence-chain.svg",
    "evidence-integrity.svg",
    "hero-architecture.svg",
    "industrial-scenarios.svg",
    "licensed-certification.svg",
    "mcp-runtime-lifecycle.svg",
    "optimization-lifecycle.svg",
    "performance-hotspot-map.svg",
    "policy-path-safety.svg",
    "process-intent-ir.svg",
    "roadmap.svg",
    "scheduler-lifecycle.svg",
    "test-matrix.svg",
    "validity-gates.svg",
    "worker-ownership-recycle.svg",
}
AI_ACCEPTANCE_ASSETS = {
    "delivery-acceptance.svg",
    "mathematical-contracts.svg",
    "native-failure-isolation.svg",
    "warm-start-trajectory.svg",
}
TEMPORARY_NAME = re.compile(
    r"(?:once|finali[sz]er|diagnostic|running|temporary|tmp-do-not-use)",
    re.IGNORECASE,
)
README_MARKERS = {
    "README.md": {
        "## 数学与工程合同",
        "## 原生失败隔离",
        "## 交付验收",
        "PENDING_REAL_ASPEN_CERTIFICATION",
        "constraint_non_finite",
        "balance_non_finite",
        "allow_nan=False",
        "inflight_singleflight",
        "retry_wait",
        "dead_letter",
    },
    "README.en.md": {
        "## Mathematical and engineering contracts",
        "## Native failure isolation",
        "## Delivery acceptance",
        "PENDING_REAL_ASPEN_CERTIFICATION",
        "constraint_non_finite",
        "balance_non_finite",
        "allow_nan=False",
        "inflight_singleflight",
        "retry_wait",
        "dead_letter",
    },
}
REQUIRED_FILES = {
    "README.md",
    "README.en.md",
    "LICENSE",
    "pyproject.toml",
    "docs/architecture.md",
    "docs/delivery-acceptance.md",
    QUALIFICATION,
    "scripts/verify_delivery.py",
    "tests/test_delivery_acceptance.py",
}


class DeliveryVerificationError(ValueError):
    pass


def _reject_constant(value: str) -> None:
    raise DeliveryVerificationError(f"Non-standard JSON constant: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DeliveryVerificationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
        parse_constant=_reject_constant,
    )


def _issue(issues: list[dict[str, str]], code: str, path: str, detail: str) -> None:
    issues.append({"code": code, "path": path, "detail": detail})


def _check_required_files(root: Path, issues: list[dict[str, str]]) -> None:
    for relative in sorted(REQUIRED_FILES):
        if not (root / relative).is_file():
            _issue(issues, "required_file_missing", relative, "Required delivery file is missing")


def _check_package(root: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    path = root / "pyproject.toml"
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        _issue(issues, "pyproject_invalid", "pyproject.toml", str(exc))
        return {}
    project = document.get("project")
    if not isinstance(project, dict):
        _issue(issues, "project_metadata_missing", "pyproject.toml", "[project] is required")
        return {}
    if project.get("name") != "aspenops-nexus":
        _issue(issues, "package_name_mismatch", "pyproject.toml", "Expected aspenops-nexus")
    if project.get("version") != "2.0.0":
        _issue(issues, "package_version_mismatch", "pyproject.toml", "Expected version 2.0.0")
    if project.get("readme") != "README.md":
        _issue(issues, "package_readme_mismatch", "pyproject.toml", "Expected README.md")
    return {"name": project.get("name"), "version": project.get("version")}


def _check_qualification(root: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    path = root / QUALIFICATION
    try:
        evidence = load_strict_json(path)
    except (OSError, json.JSONDecodeError, DeliveryVerificationError) as exc:
        _issue(issues, "qualification_invalid", QUALIFICATION, str(exc))
        return {}
    if not isinstance(evidence, dict):
        _issue(issues, "qualification_root_invalid", QUALIFICATION, "Root must be an object")
        return {}
    expected = {
        "schema": "aspenops.acceptance-hardening-qualification/v2",
        "status": "PASS",
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "reverse_order_gate": "PASS",
        "real_aspen_status": "PENDING_REAL_ASPEN_CERTIFICATION",
    }
    for key, value in expected.items():
        if evidence.get(key) != value:
            _issue(
                issues,
                "qualification_field_mismatch",
                f"{QUALIFICATION}:{key}",
                f"Expected {value!r}, observed {evidence.get(key)!r}",
            )
    passed = evidence.get("passed")
    if isinstance(passed, bool) or not isinstance(passed, int) or passed < 1200:
        _issue(issues, "qualification_test_floor", QUALIFICATION, "passed must be >= 1200")
    coverage = evidence.get("branch_coverage_percent")
    if (
        isinstance(coverage, bool)
        or not isinstance(coverage, int | float)
        or not math.isfinite(float(coverage))
        or float(coverage) < 95.0
    ):
        _issue(issues, "qualification_coverage_floor", QUALIFICATION, "coverage must be >= 95")
    seeded = evidence.get("seeded_order_gate")
    if not isinstance(seeded, dict) or seeded.get("status") != "PASS":
        _issue(issues, "seeded_order_gate_failed", QUALIFICATION, "Seeded order gate must pass")
    static = evidence.get("static_gates")
    required_static = {
        "bandit_high_high",
        "compileall",
        "mypy_strict",
        "ruff",
        "source_tree_audit",
    }
    if not isinstance(static, dict) or any(static.get(name) != "PASS" for name in required_static):
        _issue(issues, "static_gate_failed", QUALIFICATION, "Every required static gate must pass")
    return evidence


def _check_workflows(root: Path, issues: list[dict[str, str]]) -> list[str]:
    directory = root / ".github" / "workflows"
    names = {path.name for path in directory.glob("*.yml")}
    if names != AUTHORITATIVE_WORKFLOWS:
        _issue(
            issues,
            "workflow_inventory_mismatch",
            ".github/workflows",
            f"Expected {sorted(AUTHORITATIVE_WORKFLOWS)}, observed {sorted(names)}",
        )
    for path in sorted(directory.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if "contents: write" in text:
            _issue(issues, "workflow_write_permission", str(path.relative_to(root)), "Must be read-only")
        if TEMPORARY_NAME.search(path.name):
            _issue(issues, "temporary_workflow_present", str(path.relative_to(root)), path.name)
    return sorted(names)


def temporary_artifacts(root: Path) -> list[str]:
    candidates: list[str] = []
    for base in (root / ".github" / "workflows", root / "docs", root / "scripts"):
        if not base.exists():
            continue
        for path in base.iterdir():
            if path.is_file() and TEMPORARY_NAME.search(path.name):
                candidates.append(str(path.relative_to(root)))
    return sorted(candidates)


def _check_temporary_artifacts(root: Path, issues: list[dict[str, str]]) -> None:
    for path in temporary_artifacts(root):
        _issue(issues, "temporary_artifact_present", path, "Remove temporary acceptance artifact")


def _check_visuals(root: Path, issues: list[dict[str, str]]) -> list[str]:
    directory = root / "docs" / "assets" / "readme"
    names = {path.name for path in directory.glob("*.svg")}
    if names != GOVERNED_VISUAL_ASSETS:
        _issue(
            issues,
            "visual_inventory_mismatch",
            "docs/assets/readme",
            f"Expected {sorted(GOVERNED_VISUAL_ASSETS)}, observed {sorted(names)}",
        )
    ai_directory = root / "docs" / "assets" / "ai"
    ai_names = {path.name for path in ai_directory.glob("*.svg")}
    if ai_names != AI_ACCEPTANCE_ASSETS:
        _issue(
            issues,
            "ai_visual_inventory_mismatch",
            "docs/assets/ai",
            f"Expected {sorted(AI_ACCEPTANCE_ASSETS)}, observed {sorted(ai_names)}",
        )
    return sorted(names | ai_names)


def _check_readmes(root: Path, issues: list[dict[str, str]]) -> None:
    expected_paths = {f"docs/assets/readme/{name}" for name in GOVERNED_VISUAL_ASSETS}
    pattern = re.compile(r"!\[[^\]]*\]\((docs/assets/readme/[^)]+\.svg)\)")
    for relative, markers in README_MARKERS.items():
        path = root / relative
        text = path.read_text(encoding="utf-8")
        for marker in sorted(markers):
            if marker not in text:
                _issue(issues, "readme_marker_missing", f"{relative}:{marker}", marker)
        observed = set(pattern.findall(text))
        if observed != expected_paths:
            _issue(
                issues,
                "readme_visual_inventory_mismatch",
                relative,
                f"Expected {len(expected_paths)} unique SVG references; observed {len(observed)}",
            )
        for name in sorted(AI_ACCEPTANCE_ASSETS):
            if f"docs/assets/ai/{name}" not in text:
                _issue(
                    issues,
                    "readme_ai_visual_missing",
                    relative,
                    f"docs/assets/ai/{name}",
                )
        if "REAL_ASPEN_CERTIFIED" in text:
            _issue(
                issues,
                "forbidden_certification_claim",
                relative,
                "README must not claim REAL_ASPEN_CERTIFIED",
            )


def verify_delivery(root: Path = ROOT) -> dict[str, Any]:
    resolved = root.resolve()
    issues: list[dict[str, str]] = []
    _check_required_files(resolved, issues)
    package = _check_package(resolved, issues)
    qualification = _check_qualification(resolved, issues)
    workflows = _check_workflows(resolved, issues)
    _check_temporary_artifacts(resolved, issues)
    visuals = _check_visuals(resolved, issues)
    _check_readmes(resolved, issues)
    return {
        "schema": "aspenops.delivery-acceptance/v1",
        "status": "PASS" if not issues else "FAIL",
        "root": str(resolved),
        "package": package,
        "qualification": {
            "schema": qualification.get("schema"),
            "passed": qualification.get("passed"),
            "branch_coverage_percent": qualification.get("branch_coverage_percent"),
            "real_aspen_status": qualification.get("real_aspen_status"),
        },
        "workflows": workflows,
        "visual_asset_count": len(visuals),
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify AspenOps delivery acceptance contracts")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = verify_delivery(args.root)
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
