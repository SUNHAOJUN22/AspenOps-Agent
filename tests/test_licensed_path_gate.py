from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest


def load_gate() -> ModuleType:
    path = Path("scripts/validate_licensed_paths.py")
    spec = importlib.util.spec_from_file_location("validate_licensed_paths", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def environment(workspace: Path, allowed: Path, plan: Path, state: Path) -> dict[str, str]:
    return {
        "GITHUB_WORKSPACE": str(workspace),
        "PLAN_PATH": str(plan),
        "ASPENOPS_ALLOWED_ROOTS": str(allowed),
        "ASPENOPS_STATE_DIR": str(state),
    }


def test_valid_licensed_paths_are_canonicalized(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    allowed = tmp_path / "allowed"
    workspace.mkdir()
    allowed.mkdir()
    plan = workspace / "plan.json"
    plan.write_text("{}", encoding="utf-8")

    result = load_gate().validate_paths(
        environment(workspace, allowed, plan, allowed / "state")
    )

    assert result == {
        "plan_path": str(plan.resolve()),
        "state_dir": str((allowed / "state").resolve()),
    }


def test_plan_symlink_cannot_escape_the_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside.json"
    workspace.mkdir()
    allowed.mkdir()
    outside.write_text("{}", encoding="utf-8")
    link = workspace / "plan.json"
    try:
        os.symlink(outside, link)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(ValueError, match="PLAN_PATH resolves outside"):
        load_gate().validate_paths(environment(workspace, allowed, link, allowed / "state"))


def test_state_symlink_parent_cannot_escape_allowed_roots(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    workspace.mkdir()
    allowed.mkdir()
    outside.mkdir()
    plan = workspace / "plan.json"
    plan.write_text("{}", encoding="utf-8")
    link = allowed / "linked"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(ValueError, match="STATE_DIR resolves outside"):
        load_gate().validate_paths(environment(workspace, allowed, plan, link / "state"))
