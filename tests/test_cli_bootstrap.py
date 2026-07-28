from __future__ import annotations

import json
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus import cli, cli_bootstrap

ROOT = Path(__file__).resolve().parents[1]
HEAVY_MODULES = {
    "aspenops_nexus.batch",
    "aspenops_nexus.benchmark",
    "aspenops_nexus.certification",
    "aspenops_nexus.licensed_certification",
    "aspenops_nexus.mcp_server",
    "aspenops_nexus.optimization",
    "aspenops_nexus.pool",
    "aspenops_nexus.pool_manager",
    "aspenops_nexus.provenance",
    "aspenops_nexus.scheduler",
}


def _subparsers(parser: ArgumentParser) -> dict[str, ArgumentParser]:
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            return {str(name): value for name, value in choices.items()}
    raise AssertionError("CLI parser has no subcommands")


def _probe(arguments: list[str]) -> dict[str, Any]:
    code = """
import json
import sys
from aspenops_nexus import cli_bootstrap

arguments = json.loads(sys.argv[1])
try:
    cli_bootstrap.main(arguments)
except SystemExit as exc:
    exit_code = exc.code
else:
    exit_code = None
heavy = sorted(
    name
    for name in sys.modules
    if name in {
        'aspenops_nexus.batch',
        'aspenops_nexus.benchmark',
        'aspenops_nexus.certification',
        'aspenops_nexus.licensed_certification',
        'aspenops_nexus.mcp_server',
        'aspenops_nexus.optimization',
        'aspenops_nexus.pool',
        'aspenops_nexus.pool_manager',
        'aspenops_nexus.provenance',
        'aspenops_nexus.scheduler',
    }
)
print('__ASPENOPS_BOOTSTRAP__' + json.dumps({'exit_code': exit_code, 'heavy': heavy}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, json.dumps(arguments)],
        check=True,
        capture_output=True,
        text=True,
    )
    marker = next(
        line.removeprefix("__ASPENOPS_BOOTSTRAP__")
        for line in completed.stdout.splitlines()
        if line.startswith("__ASPENOPS_BOOTSTRAP__")
    )
    value = json.loads(marker)
    assert isinstance(value, dict)
    return {str(key): item for key, item in value.items()}


def test_lightweight_commands_do_not_import_execution_control_plane() -> None:
    for arguments in (["--version"], ["--help"], ["optimize", "--help"]):
        result = _probe(arguments)
        assert result["exit_code"] == 0
        assert result["heavy"] == []


def test_bootstrap_parser_matches_full_cli_surface() -> None:
    bootstrap = cli_bootstrap.build_parser()
    full = cli.build_parser()
    assert bootstrap.format_help() == full.format_help()

    bootstrap_commands = _subparsers(bootstrap)
    full_commands = _subparsers(full)
    assert bootstrap_commands.keys() == full_commands.keys()
    for name in bootstrap_commands:
        assert bootstrap_commands[name].format_help() == full_commands[name].format_help()


def test_executed_commands_delegate_without_bootstrap_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def forbidden_parser() -> ArgumentParser:
        raise AssertionError("executed commands must not be parsed by the bootstrap")

    monkeypatch.setattr(cli_bootstrap, "build_parser", forbidden_parser)
    monkeypatch.setattr(cli, "main", lambda arguments: calls.append(arguments))

    cli_bootstrap.main(["job", "job-1"])
    assert calls == [["job", "job-1"]]


def test_cli_startup_probe_writes_bounded_machine_readable_evidence(tmp_path: Path) -> None:
    output = tmp_path / "cli-startup.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/measure_cli_startup.py"),
            "--output",
            str(output),
            "--trials",
            "1",
            "--warmups",
            "0",
        ],
        check=True,
    )

    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["schema"] == "aspenops.cli-startup/v1"
    assert evidence["kind"] == "portable-python-cli-startup"
    assert "do not measure Aspen Plus/HYSYS" in evidence["boundary"]
    assert len(evidence["measurements"]) == 6
    assert len(evidence["comparisons"]) == 3
    assert len(evidence["import_profiles"]) == 2
    assert all(item["trial_count"] == 1 for item in evidence["measurements"])
    assert all(item["median_s"] >= 0.0 for item in evidence["measurements"])
    assert all(item["record_count"] > 0 for item in evidence["import_profiles"])
    assert all(item["total_self_time_us"] > 0 for item in evidence["import_profiles"])
    assert all(
        item["classification"] == "MEASURED_SAME_ENVIRONMENT" for item in evidence["comparisons"]
    )

    operation_path = output.with_name(evidence["operation_counts_artifact"])
    operation = json.loads(operation_path.read_text(encoding="utf-8"))
    assert operation["schema"] == "aspenops.operation-counts/v2"
    assert operation["pool"]["cache_key_calls"] == 1
    assert operation["pool"]["solver_calls"] == 1
    assert operation["pool"]["result_serializations"] == 1
    assert operation["memory_cache"]["json_decode_calls"] == 2
    assert operation["memory_cache"]["sqlite_connection_calls"] == 0
    assert operation["memory_cache"]["deep_result_isolation"] is True
    assert operation["memory_cache"]["strategy"] == "compact_json_snapshot"
    assert operation["memory"]["traced_peak_bytes"] >= 0
    assert operation["profile"]["total_calls"] > 0
    assert operation["profile"]["top_cumulative_functions"]
    assert "profiler overhead" in operation["profile"]["boundary"]

    query_path = output.with_name(evidence["job_store_query_plan_artifact"])
    query = json.loads(query_path.read_text(encoding="utf-8"))
    assert query["schema"] == "aspenops.job-store-query-plan/v1"
    assert query["records"] == 1000
    assert query["returned_records"] == 20
    assert query["connection_calls"] == 1
    assert query["select_statements"] == 1
    assert "idx_jobs_recent_created_job" in query["indexes"]
    assert any("idx_jobs_recent_created_job" in detail for detail in query["query_plan"])
    assert all("USE TEMP B-TREE" not in detail.upper() for detail in query["query_plan"])


def test_heavy_module_guard_is_complete() -> None:
    assert "aspenops_nexus.pool" in HEAVY_MODULES
    assert "aspenops_nexus.scheduler" in HEAVY_MODULES
    assert "aspenops_nexus.mcp_server" in HEAVY_MODULES
