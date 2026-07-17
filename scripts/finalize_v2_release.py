from __future__ import annotations

from pathlib import Path


def replace_if_present(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        return False
    path.write_text(text.replace(old, new), encoding="utf-8")
    return True


def replace_once_required(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Required release marker missing in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_versions(root: Path) -> None:
    pyproject = root / "pyproject.toml"
    replace_if_present(pyproject, 'version = "1.0.0"', 'version = "2.0.0"')
    init = root / "src/aspenops_nexus/__init__.py"
    replace_if_present(init, '__version__ = "1.0.0"', '__version__ = "2.0.0"')
    replace_if_present(
        init,
        'RUNTIME_SCHEMA = "aspenops.runtime/v1"',
        'RUNTIME_SCHEMA = "aspenops.runtime/v2"',
    )


def patch_optimization_tests(root: Path) -> None:
    path = root / "tests/test_optimization_edge_cases.py"
    if not path.exists():
        return
    replace_if_present(path, "VariableSpec.from_dict", "VariableSpec.from_mapping")
    replace_if_present(path, "ObjectiveSpec.from_dict", "ObjectiveSpec.from_mapping")
    replace_if_present(path, "OptimizationBudget.from_dict", "OptimizationBudget.from_mapping")


def patch_readme(root: Path) -> None:
    for relative in ("README.md", "README.en.md"):
        path = root / relative
        if not path.exists():
            continue
        replacements = {
            "AspenOps 1.0": "AspenOps 2.0",
            "version-1.0.0": "version-2.0.0",
            "immutable evidence bundle": "self-checking integrity bundle",
            "immutable run evidence": "self-checking run integrity evidence",
            "不可篡改运行证据包": "自校验运行完整性包",
            "防篡改运行证据包": "自校验运行完整性包",
            "防篡改": "自校验完整性",
        }
        for old, new in replacements.items():
            replace_if_present(path, old, new)


def patch_changelog(root: Path) -> None:
    path = root / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    if "## 2.0.0" in text:
        return
    section = """# Changelog

## 2.0.0 - 2026-07-18

- fail-closed convergence evidence for Aspen Plus and HYSYS;
- verified write rollback with tainted Worker recycling;
- compiled unique-node evaluation plans and cache-source provenance;
- cross-call singleflight and persistent license-aware CasePools;
- leased durable jobs, heartbeats, cancellation deadlines and idempotent commits;
- Windows Job Object supervision with process-fingerprint fallback;
- member-level integrity manifests and optional Ed25519 signatures;
- budgeted batch constrained optimization with mixed variables and Pareto results;
- portable baseline/candidate benchmark evidence and expanded CI contracts.

"""
    if text.startswith("# Changelog\n"):
        text = section + text[len("# Changelog\n\n") :]
    else:
        text = section + text
    path.write_text(text, encoding="utf-8")


def patch_env(root: Path) -> None:
    path = root / ".env.example"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    additions = """
ASPENOPS_MAX_RESIDENT_CASES=2
ASPENOPS_POOL_IDLE_TIMEOUT_S=1800
ASPENOPS_JOB_LEASE_S=30
ASPENOPS_CANCELLATION_GRACE_S=2
ASPENOPS_JOB_MAX_ATTEMPTS=3
"""
    if "ASPENOPS_MAX_RESIDENT_CASES" not in text:
        path.write_text(text.rstrip() + "\n" + additions.lstrip(), encoding="utf-8")


def patch_ci(root: Path) -> None:
    path = root / ".github/workflows/ci.yml"
    text = path.read_text(encoding="utf-8")
    if "Ruff format" not in text:
        marker = "      - name: Strict mypy\n"
        insertion = (
            "      - name: Ruff format\n"
            "        run: uv run ruff format --check .\n"
        )
        if marker not in text:
            raise RuntimeError("Unable to add Ruff format gate")
        text = text.replace(marker, insertion + marker, 1)
    text = text.replace(
        "--cov=aspenops_nexus \\\n            --cov-report=term \\",
        "--cov=aspenops_nexus \\\n            --cov-branch \\\n            --cov-report=term \\",
    )
    if "Benchmark smoke" not in text:
        marker = "      - name: Verify MCP surface\n"
        insertion = (
            "      - name: Benchmark smoke\n"
            "        run: uv run python scripts/run_benchmark_matrix.py "
            "--repo-root . --output var/ci/benchmark-smoke.json --smoke\n"
            "      - name: Wheel install smoke\n"
            "        if: matrix.python-version == '3.12'\n"
            "        shell: bash\n"
            "        run: |\n"
            "          python -m venv /tmp/aspenops-wheel\n"
            "          /tmp/aspenops-wheel/bin/pip install dist/*.whl\n"
            "          /tmp/aspenops-wheel/bin/aspenops --version\n"
        )
        if marker not in text:
            raise RuntimeError("Unable to add benchmark and wheel gates")
        text = text.replace(marker, insertion + marker, 1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    required_markers = {
        "src/aspenops_nexus/optimization.py": "ObjectMap: TypeAlias",
        "src/aspenops_nexus/mcp_server.py": "def submit_optimization",
        "src/aspenops_nexus/worker.py": "WindowsJobScope",
    }
    for relative, marker in required_markers.items():
        path = root / relative
        if not path.exists() or marker not in path.read_text(encoding="utf-8"):
            raise RuntimeError(f"Release prerequisite missing: {relative} -> {marker}")
    patch_versions(root)
    patch_optimization_tests(root)
    patch_readme(root)
    patch_changelog(root)
    patch_env(root)
    patch_ci(root)
    (root / "scripts/finalize_v2_release.py").unlink(missing_ok=True)
    (root / ".github/workflows/finalize-v2-release.yml").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
