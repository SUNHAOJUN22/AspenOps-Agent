from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = runpy.run_path(
    str(ROOT / "scripts" / "run_six_repository_active_gate_v4.py")
)
COMMANDS = NAMESPACE["COMMANDS"]


def test_resindb_active_cycle_includes_real_browser_gate() -> None:
    commands = COMMANDS["resindb"]

    assert commands[-2] == ("npm", "run", "build")
    assert commands[-1] == ("npm", "run", "test:ui")
    assert commands.count(("npm", "run", "test:ui")) == 1


def test_all_active_commands_are_immutable_argument_vectors() -> None:
    forbidden = ("&&", "||", ";", "shell=True")

    for group in COMMANDS.values():
        assert isinstance(group, tuple)
        assert group
        for command in group:
            assert isinstance(command, tuple)
            assert command
            assert all(isinstance(argument, str) and argument for argument in command)
            assert not any(
                token in argument for token in forbidden for argument in command
            )
