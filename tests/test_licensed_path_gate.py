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


def environment(
    workspace: Path | str,
    allowed: Path | str,
    plan: Path | str,
    state: Path | str,
) -> dict[str, str]:
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

    result = load_gate().validate_paths(environment(workspace, allowed, plan, allowed / "state"))

    assert result == {
        "plan_path": str(plan.resolve()),
        "state_dir": str((allowed / "state").resolve()),
    }


def test_multiple_absolute_roots_are_supported(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    first = tmp_path / "first"
    second = tmp_path / "second"
    workspace.mkdir()
    first.mkdir()
    second.mkdir()
    plan = workspace / "plan.json"
    plan.write_text("{}", encoding="utf-8")

    result = load_gate().validate_paths(
        environment(workspace, f"{first};{second}", plan, second / "state")
    )

    assert result["state_dir"] == str((second / "state").resolve())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "GITHUB_WORKSPACE",
            "relative-workspace",
            "GITHUB_WORKSPACE must be absolute",
        ),
        (
            "ASPENOPS_ALLOWED_ROOTS",
            "relative-root",
            "ALLOWED_ROOTS entry must be absolute",
        ),
        (
            "ASPENOPS_STATE_DIR",
            "relative-state",
            "STATE_DIR must be absolute",
        ),
    ],
)
def test_control_paths_must_be_explicitly_absolute(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    workspace = tmp_path / "workspace"
    allowed = tmp_path / "allowed"
    workspace.mkdir()
    allowed.mkdir()
    plan = workspace / "plan.json"
    plan.write_text("{}", encoding="utf-8")
    data = environment(workspace, allowed, plan, allowed / "state")
    data[field] = value

    with pytest.raises(ValueError, match=message):
        load_gate().validate_paths(data)


def test_allowed_root_must_be_an_existing_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    plan = workspace / "plan.json"
    plan.write_text("{}", encoding="utf-8")
    root_file = tmp_path / "not-a-directory"
    root_file.write_text("x", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="ALLOWED_ROOTS entry must be an existing directory",
    ):
        load_gate().validate_paths(environment(workspace, root_file, plan, tmp_path / "state"))


def test_existing_state_target_must_be_a_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    allowed = tmp_path / "allowed"
    workspace.mkdir()
    allowed.mkdir()
    plan = workspace / "plan.json"
    plan.write_text("{}", encoding="utf-8")
    state_file = allowed / "state"
    state_file.write_text("not-a-directory", encoding="utf-8")

    with pytest.raises(ValueError, match="STATE_DIR must identify a directory"):
        load_gate().validate_paths(environment(workspace, allowed, plan, state_file))


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
