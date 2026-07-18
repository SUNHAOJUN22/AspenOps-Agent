from __future__ import annotations

import runpy
from pathlib import Path


TEMPORARY_FILES = (
    ".github/workflows/apply-optimization-interfaces.yml",
    ".github/workflows/apply-process-supervision.yml",
    ".github/workflows/consolidate-v2.yml",
    ".github/workflows/finalize-v2-release.yml",
    "scripts/apply_optimization_interfaces.py",
    "scripts/apply_process_supervision.py",
    "scripts/consolidate_v2.py",
    "scripts/finalize_v2_release.py",
)


def run_if_present(root: Path, relative: str) -> None:
    path = root / relative
    if path.exists():
        runpy.run_path(str(path), run_name="__main__")


def replace_if_present(path: Path, old: str, new: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if old in text:
        path.write_text(text.replace(old, new), encoding="utf-8")


def normalize_staged_migrations(root: Path) -> None:
    supervision = root / "scripts/apply_process_supervision.py"
    replace_if_present(
        supervision,
        "# Only processes created after this worker opened its document are eligible for cleanup.",
        "# This remains a compatibility fallback until Windows Job Object ownership is certified.",
    )


def enforce_release_identity(root: Path) -> None:
    replace_if_present(root / "pyproject.toml", 'version = "1.0.0"', 'version = "2.0.0"')
    init = root / "src/aspenops_nexus/__init__.py"
    replace_if_present(init, "AspenOps 1.0", "AspenOps 2.0")
    replace_if_present(init, '__version__ = "1.0.0"', '__version__ = "2.0.0"')
    replace_if_present(
        init,
        'RUNTIME_SCHEMA = "aspenops.runtime/v1"',
        'RUNTIME_SCHEMA = "aspenops.runtime/v2"',
    )
    replace_if_present(
        root / "src/aspenops_nexus/cli.py",
        "AspenOps 1.0 deterministic execution fabric",
        "AspenOps 2.0 deterministic execution fabric",
    )


def remove_temporary_files(root: Path) -> None:
    for relative in TEMPORARY_FILES:
        (root / relative).unlink(missing_ok=True)


def validate_markers(root: Path) -> None:
    required = {
        "src/aspenops_nexus/optimization.py": (
            "ObjectMap: TypeAlias",
            "pool_observer",
        ),
        "src/aspenops_nexus/mcp_server.py": (
            "def submit_optimization",
            "def cancel_optimization",
        ),
        "src/aspenops_nexus/worker.py": ("WindowsJobScope",),
        "src/aspenops_nexus/backends/aspen_plus.py": ("owned_processes", "job_managed"),
    }
    failures: list[str] = []
    for relative, markers in required.items():
        path = root / relative
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        for marker in markers:
            if marker not in text:
                failures.append(f"{relative}: {marker}")
    if failures:
        raise RuntimeError("Consolidation markers missing: " + " | ".join(failures))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    normalize_staged_migrations(root)
    run_if_present(root, "scripts/consolidate_v2.py")
    run_if_present(root, "scripts/apply_optimization_interfaces.py")
    run_if_present(root, "scripts/apply_process_supervision.py")
    run_if_present(root, "scripts/finalize_v2_release.py")
    enforce_release_identity(root)
    remove_temporary_files(root)
    validate_markers(root)
    (root / "scripts/autonomous_consolidate.py").unlink(missing_ok=True)
    (root / ".github/workflows/autonomous-consolidate.yml").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
