from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError(f"{name} must be one non-empty line")
    return value


def _within(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def validate_paths(environment: Mapping[str, str]) -> dict[str, str]:
    workspace_path = Path(_required(environment, "GITHUB_WORKSPACE")).expanduser()
    if not workspace_path.is_absolute():
        raise ValueError("GITHUB_WORKSPACE must be absolute")
    workspace = workspace_path.resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("GITHUB_WORKSPACE must identify an existing directory")

    plan = Path(_required(environment, "PLAN_PATH")).expanduser().resolve(strict=True)
    if not plan.is_file():
        raise ValueError("PLAN_PATH must identify an existing file")
    if not _within(plan, (workspace,)):
        raise ValueError("PLAN_PATH resolves outside GITHUB_WORKSPACE")

    root_values = tuple(
        item.strip()
        for item in _required(environment, "ASPENOPS_ALLOWED_ROOTS").split(";")
        if item.strip()
    )
    if not root_values:
        raise ValueError("ASPENOPS_ALLOWED_ROOTS must contain at least one root")
    root_paths = tuple(Path(item).expanduser() for item in root_values)
    if any(not root.is_absolute() for root in root_paths):
        raise ValueError("Every ASPENOPS_ALLOWED_ROOTS entry must be absolute")
    roots = tuple(root.resolve(strict=True) for root in root_paths)
    if any(not root.is_dir() for root in roots):
        raise ValueError("Every ASPENOPS_ALLOWED_ROOTS entry must be an existing directory")

    state_path = Path(_required(environment, "ASPENOPS_STATE_DIR")).expanduser()
    if not state_path.is_absolute():
        raise ValueError("ASPENOPS_STATE_DIR must be absolute")
    state_dir = state_path.resolve(strict=False)
    if state_dir.exists() and not state_dir.is_dir():
        raise ValueError("ASPENOPS_STATE_DIR must identify a directory")
    if not _within(state_dir, roots):
        raise ValueError("ASPENOPS_STATE_DIR resolves outside ASPENOPS_ALLOWED_ROOTS")

    return {
        "plan_path": str(plan),
        "state_dir": str(state_dir),
    }


def main() -> None:
    result: dict[str, Any] = validate_paths(os.environ)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
