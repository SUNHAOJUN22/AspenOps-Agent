from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from zipfile import ZipFile

import aspenops_nexus.mcp_server as mcp_server
from aspenops_nexus.wheel_metadata import inspect_wheel

ROOT = Path(__file__).resolve().parents[1]


def test_wheel_smoke_uses_hashed_locked_runtime_dependencies() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    export_block = text[
        text.index("uv export --frozen") : text.index("uv venv --python 3.12")
    ]

    assert "--extra agent" in export_block
    assert "--no-default-groups" in export_block
    assert "--no-emit-project" in export_block
    assert "--format requirements.txt" in export_block
    assert "--output-file var/ci/runtime-requirements.txt" in export_block
    assert "uv pip sync" in text
    assert "--require-hashes" in text
    assert "uv pip install" in text
    assert "--offline" in text
    assert "--no-deps" in text
    assert "uv pip check --python /tmp/aspenops-wheel/bin/python" in text
    assert "/tmp/aspenops-wheel/bin/aspenops scheduler --help" in text
    assert "/tmp/aspenops-wheel/bin/aspenops cancel --help" in text
    assert "/tmp/aspenops-wheel/bin/aspenops optimize --help" in text
    assert "_require_supported_mcp_sdk" in text
    assert "wheel-mcp-version.log" in text
    assert "tests/test_cli_durable_queue.py" in text
    assert "uv run aspenops submit examples/batch-request.example.json" in text
    assert 'data["paths_pinned"] is True' in text
    assert "uv run aspenops cancel \"$job_id\" --grace-s 0" in text
    assert "uv run aspenops optimize examples/optimization-request.example.json" in text
    assert "/tmp/aspenops-wheel/bin/pip install dist/*.whl" not in text

    assert text.index("- name: Build distributions") < text.index("- name: Verify MCP surface")
    checker = Path("scripts/check_mcp.py").read_text(encoding="utf-8")
    assert "inspect_wheel" in checker
    assert 'Path("dist")' in checker
    assert "if dist_dir.exists():" in checker
    assert '"wheel_metadata": wheel_metadata' in checker


def test_mcp_runtime_lock_package_and_docs_remain_compatible() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    agent_requirements = project["project"]["optional-dependencies"]["agent"]
    assert agent_requirements == ["mcp>=1.9,<2"]
    assert project["project"]["scripts"]["aspenops"] == (
        "aspenops_nexus.cli_bootstrap:main"
    )

    lock = tomllib.loads(Path("uv.lock").read_text(encoding="utf-8"))
    packages = lock.get("package", [])
    versions = [str(package["version"]) for package in packages if package.get("name") == "mcp"]
    assert versions == ["1.28.1"]
    assert mcp_server._require_supported_mcp_sdk() == "1.28.1"

    major, minor, patch = (int(part) for part in versions[0].split("."))
    assert major == mcp_server.SUPPORTED_MCP_MAJOR == 1
    assert (major, minor, patch) >= (1, 9, 0)

    server = Path("src/aspenops_nexus/mcp_server.py").read_text(encoding="utf-8")
    assert "SUPPORTED_MCP_MAJOR = 1" in server
    assert 'MCP_INSTALL_CONSTRAINT = "mcp>=1.9,<2"' in server
    assert "_require_supported_mcp_sdk" in server
    assert "_scheduler_lifespan" in server

    for readme in (Path("README.md"), Path("README.en.md")):
        text = readme.read_text(encoding="utf-8")
        assert "mcp>=1.9,<2" in text
        assert "mcp-runtime-lifecycle.svg" in text


def test_built_wheel_metadata_parser_runs_on_every_software_gate(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel = dist_dir / "aspenops_nexus-2.0.0-py3-none-any.whl"
    metadata = "\n".join(
        [
            "Metadata-Version: 2.4",
            "Name: aspenops-nexus",
            "Version: 2.0.0",
            "Requires-Dist: mcp<2,>=1.9; extra == 'agent'",
            "",
        ]
    )
    with ZipFile(wheel, "w") as archive:
        archive.writestr("aspenops_nexus-2.0.0.dist-info/METADATA", metadata)

    report = inspect_wheel(dist_dir)
    assert report["ok"] is True
    assert report["wheel"] == wheel.name


def test_lazy_cli_version_path_runs_without_heavy_control_plane_imports() -> None:
    code = """
import json
import sys
from aspenops_nexus import cli_bootstrap
try:
    cli_bootstrap.main(['--version'])
except SystemExit as exc:
    exit_code = exc.code
else:
    exit_code = None
heavy = sorted(name for name in sys.modules if name in {
    'aspenops_nexus.optimization',
    'aspenops_nexus.pool',
    'aspenops_nexus.pool_manager',
    'aspenops_nexus.provenance',
    'aspenops_nexus.scheduler',
})
print('__RESULT__' + json.dumps({'exit_code': exit_code, 'heavy': heavy}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    marker = next(
        line.removeprefix("__RESULT__")
        for line in completed.stdout.splitlines()
        if line.startswith("__RESULT__")
    )
    assert json.loads(marker) == {"exit_code": 0, "heavy": []}


def test_operation_count_probe_runs_on_every_software_gate(tmp_path: Path) -> None:
    output = tmp_path / "operation-counts.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/measure_operation_counts.py"),
            "--output",
            str(output),
        ],
        check=True,
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["schema"] == "aspenops.operation-counts/v2"
    assert report["pool"]["cache_key_calls"] == 1
    assert report["pool"]["solver_calls"] == 1
    assert report["pool"]["result_serializations"] == 1
    assert report["pool"]["same_batch_dedup_results"] == 99
    assert report["pool"]["deep_result_isolation"] is True
    assert report["cache"]["pending_hit_total_after_threshold"] == 0
    assert report["memory_cache"]["json_decode_calls"] == 0
    assert report["memory_cache"]["sqlite_connection_calls"] == 0
    assert report["memory_cache"]["deep_result_isolation"] is True
    assert report["pareto"]["dominance_calls"] == 0
    assert report["memory"]["traced_peak_bytes"] >= 0
    assert report["profile"]["total_calls"] > 0
    assert report["profile"]["top_cumulative_functions"]
    assert "profiler overhead" in report["profile"]["boundary"]


def test_job_store_query_plan_runs_on_every_software_gate(tmp_path: Path) -> None:
    output = tmp_path / "job-store-query-plan.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/measure_job_store_queries.py"),
            "--output",
            str(output),
            "--records",
            "1000",
            "--limit",
            "20",
        ],
        check=True,
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["schema"] == "aspenops.job-store-query-plan/v1"
    assert report["records"] == 1000
    assert report["returned_records"] == 20
    assert report["connection_calls"] == 1
    assert report["select_statements"] == 1
    assert "idx_jobs_recent_created_job" in report["indexes"]
    assert any("idx_jobs_recent_created_job" in detail for detail in report["query_plan"])
    assert all("USE TEMP B-TREE" not in detail.upper() for detail in report["query_plan"])


def test_mcp_lifespan_starts_and_stops_the_owned_scheduler() -> None:
    events: list[str] = []

    class FakeScheduler:
        def start(self) -> None:
            events.append("start")

        def stop(self) -> None:
            events.append("stop")

    async def exercise() -> None:
        async with mcp_server._scheduler_lifespan(
            None,
            scheduler=FakeScheduler(),  # type: ignore[arg-type]
            start_scheduler=True,
        ):
            events.append("serve")

    asyncio.run(exercise())
    assert events == ["start", "serve", "stop"]
