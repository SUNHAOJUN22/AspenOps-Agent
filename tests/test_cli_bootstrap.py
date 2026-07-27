from __future__ import annotations

import json
import subprocess
import sys
from argparse import ArgumentParser
from typing import Any

from aspenops_nexus import cli, cli_bootstrap

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


def test_heavy_module_guard_is_complete() -> None:
    assert "aspenops_nexus.pool" in HEAVY_MODULES
    assert "aspenops_nexus.scheduler" in HEAVY_MODULES
    assert "aspenops_nexus.mcp_server" in HEAVY_MODULES
