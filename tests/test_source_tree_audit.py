from __future__ import annotations

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_source_tree.py"
NAMESPACE = runpy.run_path(str(SCRIPT))
audit_tree = NAMESPACE["audit_tree"]
main = NAMESPACE["main"]


def test_repository_source_tree_has_no_forbidden_constructs() -> None:
    report = audit_tree(ROOT)

    assert report["status"] == "PASS"
    assert report["totals"]["files"] >= 50
    assert report["totals"]["lines"] > 5000
    assert report["totals"]["functions"] > 100
    assert report["forbidden_findings"] == []
    json.dumps(report, allow_nan=False)


def test_audit_detects_dynamic_execution_deserialization_and_shell(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "unsafe.py").write_text(
        "import pickle\n"
        "import subprocess\n"
        "value = eval('1 + 1')\n"
        "payload = pickle.loads(b'bad')\n"
        "subprocess.run('echo bad', shell=True)\n",
        encoding="utf-8",
    )

    report = audit_tree(tmp_path)
    kinds = {item["kind"] for item in report["forbidden_findings"]}

    assert report["status"] == "FAIL"
    assert {"dynamic_eval", "unsafe_deserialization", "subprocess_shell"} <= kinds


def test_broad_exception_is_advisory_not_a_false_security_pass(tmp_path: Path) -> None:
    source = tmp_path / "scripts"
    source.mkdir()
    (source / "boundary.py").write_text(
        "def boundary():\n    try:\n        return 1\n    except Exception:\n        return 0\n",
        encoding="utf-8",
    )

    report = audit_tree(tmp_path)

    assert report["status"] == "PASS"
    assert report["forbidden_findings"] == []
    assert [item["kind"] for item in report["advisory_findings"]] == ["broad_exception_handler"]


def test_audit_cli_writes_machine_readable_failure(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "unsafe.py").write_text("exec('pass')\n", encoding="utf-8")
    output = tmp_path / "audit.json"

    assert main(["--root", str(tmp_path), "--output", str(output)]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    assert report["forbidden_findings"][0]["kind"] == "dynamic_exec"


def test_ci_persists_compile_audit_and_evidence_based_coverage_floors() -> None:
    linux = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    windows = (ROOT / ".github" / "workflows" / "windows-control-plane.yml").read_text(
        encoding="utf-8"
    )

    for workflow in (linux, windows):
        assert "python -m compileall -q src scripts" in workflow
        assert "scripts/audit_source_tree.py" in workflow
    assert 'coverage-floor: "95.0"' in linux
    assert linux.count('coverage-floor: "94.5"') == 2
    assert "--cov-fail-under=${{ matrix.coverage-floor }}" in linux
