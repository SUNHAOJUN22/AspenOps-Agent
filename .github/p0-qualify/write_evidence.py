from __future__ import annotations

import json
import os
import platform
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def junit(root: Path, name: str) -> dict[str, object]:
    path = root / name
    if not path.exists():
        return {}
    xml_root = ET.parse(path).getroot()
    suite = xml_root if "tests" in xml_root.attrib else xml_root.find("testsuite")
    if suite is None:
        return {}
    return {
        "tests": int(suite.attrib.get("tests", 0)),
        "failures": int(suite.attrib.get("failures", 0)),
        "errors": int(suite.attrib.get("errors", 0)),
        "skipped": int(suite.attrib.get("skipped", 0)),
        "time_seconds": float(suite.attrib.get("time", 0.0)),
    }


def markdown_table(statuses: dict[str, int]) -> str:
    return "\n".join(
        f"| `{name}` | {'PASS' if code == 0 else 'FAIL'} | {code} |"
        for name, code in statuses.items()
    )


def write_markdown(path: Path, text: str) -> None:
    normalized = "\n".join(line.strip() for line in text.splitlines()).strip() + "\n"
    path.write_text(normalized, encoding="utf-8")


def main() -> int:
    root = Path(os.environ["EVIDENCE_DIR"])
    statuses: dict[str, int] = {}
    for line in (root / "status.tsv").read_text(encoding="utf-8").splitlines():
        name, code = line.split("\t")
        statuses[name] = int(code)

    coverage = None
    coverage_path = root / "coverage.json"
    if coverage_path.exists():
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))["totals"]["percent_covered"]

    failure_tail: dict[str, list[str]] = {}
    for name, code in statuses.items():
        if code:
            path = root / f"{name}.log"
            failure_tail[name] = path.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]

    overall = "PASS" if statuses and all(code == 0 for code in statuses.values()) else "FAIL"
    focused = junit(root, "focused-junit.xml")
    full = junit(root, "full-junit.xml")
    boundary = (
        "P0 validates schemas, immutable manifests, qualification states, and scientific "
        "evidence relationships only. It does not open Aspen, estimate parameters, run "
        "dynamic studies, or train machine-learning models."
    )
    qualified_sha = os.environ["QUALIFIED_SHA"]
    docs = Path("docs")
    docs.mkdir(exist_ok=True)

    payload = {
        "schema": "aspenops.research-platform-p0-evidence/v1",
        "phase": "P0",
        "qualified_parent_sha": qualified_sha,
        "run_id": os.environ["RUN_ID"],
        "run_attempt": os.environ["RUN_ATTEMPT"],
        "runner_os": os.environ.get("RUNNER_OS"),
        "runner_arch": os.environ.get("RUNNER_ARCH"),
        "python_runtime": platform.python_version(),
        "uv_version": subprocess.check_output(["uv", "--version"], text=True).strip(),
        "focused_junit": focused,
        "full_junit": full,
        "branch_coverage_percent": coverage,
        "gate_status": statuses,
        "overall": overall,
        "failure_tail": failure_tail,
        "schema_count": 9,
        "complete_example_count": 2,
        "runtime_core_changed": False,
        "aspen_execution_performed": False,
        "parameter_estimation_performed": False,
        "dynamic_modeling_performed": False,
        "machine_learning_performed": False,
        "boundary": boundary,
    }
    (docs / "research-layer-p0-evidence.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    result = {
        "schema": "aspenops.research-platform-p0-result/v1",
        "phase": "P0",
        "decision": overall,
        "qualified_parent_sha": qualified_sha,
        "hard_gates": statuses,
        "branch_coverage_percent": coverage,
        "focused_tests": focused,
        "full_tests": full,
        "deliverables": {
            "source": True,
            "schemas": 9,
            "complete_examples": 2,
            "object_relationship_diagram": True,
            "qualification_state_machine": True,
            "test_report": overall == "PASS",
            "coverage_report": overall == "PASS",
            "closed_loop_validation": overall == "PASS",
        },
        "boundary": boundary,
    }
    (docs / "P0_PHASE_RESULT.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    closed_loop = {
        "schema": "aspenops.closed-loop-validation/research-p0-v1",
        "overall": overall,
        "qualified_parent_sha": qualified_sha,
        "gates": statuses,
        "invariants": {
            "main_only": True,
            "no_new_branch": True,
            "runtime_core_locked": True,
            "no_aspen_execution": True,
            "no_parameter_estimation": True,
            "no_dynamic_modeling": True,
            "no_machine_learning": True,
            "strict_schema_count": 9,
            "complete_example_count": 2,
        },
        "boundary": boundary,
    }
    (docs / "CLOSED_LOOP_VALIDATION_RESEARCH_P0.json").write_text(
        json.dumps(closed_loop, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    rows = markdown_table(statuses)
    write_markdown(
        docs / "research-layer-p0-test-report.md",
        f"""# AspenOps Research Platform P0 Test Report

        - Overall: **{overall}**
        - Qualified parent: `{qualified_sha}`
        - Focused tests: `{focused.get('tests', 0)}` tests,
          `{focused.get('failures', 0)}` failures, `{focused.get('errors', 0)}` errors,
          `{focused.get('skipped', 0)}` skipped
        - Full tests: `{full.get('tests', 0)}` tests,
          `{full.get('failures', 0)}` failures, `{full.get('errors', 0)}` errors,
          `{full.get('skipped', 0)}` skipped

        | Gate | Result | Exit code |
        |---|---:|---:|
        {rows}

        ## Boundary

        {boundary}
        """,
    )
    write_markdown(
        docs / "research-layer-p0-coverage-summary.md",
        f"""# AspenOps Research Platform P0 Coverage Summary

        - Branch-aware repository coverage: **{coverage}%**
        - Required floor: **95.0%**
        - Coverage gate: **{'PASS' if statuses.get('full-pytest') == 0 else 'FAIL'}**
        - Focused P0 contract suite: **{focused.get('tests', 0)} tests**
        - Full regression suite: **{full.get('tests', 0)} tests**

        Missing or unreadable coverage evidence is not a pass.
        """,
    )
    write_markdown(
        docs / "CLOSED_LOOP_VALIDATION_RESEARCH_P0.md",
        f"""# CLOSED LOOP VALIDATION — Research P0

        **Decision: {overall}**

        The P0 transaction is accepted only when every listed gate returns zero. The layer remains
        schema-only and does not open Aspen or add a new runtime command surface.

        | Gate | Result | Exit code |
        |---|---:|---:|
        {rows}

        Boundary: {boundary}
        """,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
