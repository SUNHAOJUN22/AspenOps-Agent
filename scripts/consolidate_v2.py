from __future__ import annotations

import runpy
from pathlib import Path


def remove_pair(root: Path, script: str, workflow: str) -> None:
    (root / script).unlink(missing_ok=True)
    (root / workflow).unlink(missing_ok=True)


def apply_if_needed(
    root: Path,
    *,
    marker_file: str,
    marker: str,
    script: str,
    workflow: str,
) -> None:
    target = root / marker_file
    if target.exists() and marker in target.read_text(encoding="utf-8"):
        remove_pair(root, script, workflow)
        return
    script_path = root / script
    if not script_path.exists():
        raise RuntimeError(f"Migration target is missing and no staged script exists: {marker}")
    runpy.run_path(str(script_path), run_name="__main__")
    if marker not in target.read_text(encoding="utf-8"):
        raise RuntimeError(f"Migration did not produce expected marker: {marker}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    apply_if_needed(
        root,
        marker_file="src/aspenops_nexus/optimization.py",
        marker="ObjectMap: TypeAlias",
        script="scripts/apply_optimization_strict_types.py",
        workflow=".github/workflows/apply-optimization-strict-types.yml",
    )
    apply_if_needed(
        root,
        marker_file="src/aspenops_nexus/mcp_server.py",
        marker="def submit_optimization",
        script="scripts/apply_optimization_interfaces.py",
        workflow=".github/workflows/apply-optimization-interfaces.yml",
    )
    apply_if_needed(
        root,
        marker_file="src/aspenops_nexus/worker.py",
        marker="WindowsJobScope",
        script="scripts/apply_process_supervision.py",
        workflow=".github/workflows/apply-process-supervision.yml",
    )
    remove_pair(
        root,
        "scripts/consolidate_v2.py",
        ".github/workflows/consolidate-v2.yml",
    )


if __name__ == "__main__":
    main()
