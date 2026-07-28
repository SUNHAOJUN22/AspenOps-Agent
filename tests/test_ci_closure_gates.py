from __future__ import annotations

import hashlib
import json
import runpy
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
ORDER_GATE = ROOT / "scripts" / "run_test_order_gate.py"
PYPROJECT = ROOT / "pyproject.toml"
UV_LOCK = ROOT / "uv.lock"
LOCK_EVIDENCE = ROOT / "docs" / "lock-sync-evidence.json"


def _normalized_text_sha256(path: Path) -> str:
    normalized = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def test_order_helpers_are_deterministic_and_non_mutating() -> None:
    namespace = runpy.run_path(str(ORDER_GATE))
    reverse_order = namespace["_reverse_order"]
    random_order = namespace["_random_order"]
    original = ["a::test_one", "b::test_two", "c::test_three", "d::test_four"]

    assert reverse_order(original) == list(reversed(original))
    assert random_order(original, 20260728) == random_order(original, 20260728)
    assert sorted(random_order(original, 20260728)) == sorted(original)
    assert original == ["a::test_one", "b::test_two", "c::test_three", "d::test_four"]


def test_ci_has_fail_closed_exact_bandit_gate() -> None:
    text = CI.read_text(encoding="utf-8")

    assert "Bandit security analysis" in text
    assert "bandit==1.9.4" in text
    assert "--isolated" in text
    assert "--recursive src scripts" in text
    assert "--severity-level high" in text
    assert "--confidence-level high" in text
    assert "--format json" in text
    assert "var/ci/bandit.json" in text
    assert "python -m json.tool var/ci/bandit.json" in text
    assert "--exit-zero" not in text


def test_ci_runs_complete_reverse_and_seeded_random_order_gate() -> None:
    workflow = CI.read_text(encoding="utf-8")
    script = ORDER_GATE.read_text(encoding="utf-8")

    assert "Verify complete-suite order independence" in workflow
    assert "matrix.python-version == '3.12'" in workflow
    assert "scripts/run_test_order_gate.py" in workflow
    assert "--seed 20260728" in workflow
    assert "--output-dir var/ci" in workflow
    assert "--collect-only" in script
    assert "addopts=" in script
    assert "error::ResourceWarning" in script
    assert 'label="reverse"' in script
    assert 'label=f"random-{args.seed}"' in script


def test_frozen_mcp_boundary_and_lock_evidence_are_current() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    agent_requirements = project["project"]["optional-dependencies"]["agent"]
    requirement = next(item for item in agent_requirements if item.startswith("mcp"))
    lock_text = UV_LOCK.read_text(encoding="utf-8")
    evidence = json.loads(LOCK_EVIDENCE.read_text(encoding="utf-8"))

    assert requirement == "mcp>=1.9,<2"
    assert 'name = "mcp", marker = "extra == \'agent\'", specifier = ">=1.9,<2"' in lock_text
    assert evidence["schema"] == "aspenops.lock-sync/v1"
    assert evidence["lock_check"] == "PASS"
    assert evidence["mcp_requirement"] == requirement
    assert evidence["uv_version"].startswith("uv 0.11.16 ")
    assert evidence["hash_normalization"] == "text-newlines-lf"
    assert evidence["pyproject_sha256"] == _normalized_text_sha256(PYPROJECT)
    assert evidence["uv_lock_sha256"] == _normalized_text_sha256(UV_LOCK)
