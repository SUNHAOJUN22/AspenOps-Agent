from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = runpy.run_path(str(ROOT / "scripts" / "run_six_repository_active_gate.py"))
COMMANDS = NAMESPACE["COMMANDS"]
command_identity = NAMESPACE["command_identity"]
execute_cycle = NAMESPACE["execute_cycle"]
read_previous = NAMESPACE["read_previous"]
run_stage = NAMESPACE["run_stage"]


def test_formal_commands_are_immutable_shell_free_argument_vectors() -> None:
    forbidden = ("&&", "||", ";", "shell=True")

    assert set(COMMANDS) == {
        "aspenops",
        "scicomputation",
        "processing",
        "resindb",
        "dft",
        "researcher",
    }
    for group in COMMANDS.values():
        assert isinstance(group, tuple)
        assert group
        for command in group:
            assert isinstance(command, tuple)
            assert command
            assert all(isinstance(argument, str) and argument for argument in command)
            assert not any(token in argument for token in forbidden for argument in command)


def test_command_identity_is_deterministic_and_order_sensitive() -> None:
    commands = (("python", "-m", "pytest"), ("python", "gate.py"))

    assert command_identity(commands) == command_identity(commands)
    assert command_identity(commands) != command_identity(tuple(reversed(commands)))


def test_execute_cycle_stops_at_first_failure(tmp_path: Path) -> None:
    sentinel = tmp_path / "must-not-run.txt"
    commands = (
        (sys.executable, "-c", "print('first-pass')"),
        (sys.executable, "-c", "raise SystemExit(7)"),
        (sys.executable, "-c", f"from pathlib import Path; Path({str(sentinel)!r}).write_text('bad')"),
    )

    returncode, output, active_ns = execute_cycle(commands)

    assert returncode == 7
    assert active_ns > 0
    assert b"first-pass" in output
    assert not sentinel.exists()


def test_read_previous_requires_pass_and_exact_sha(tmp_path: Path) -> None:
    tested_sha = "a" * 40
    summary = tmp_path / "stage-one.json"
    summary.write_text(
        json.dumps(
            {
                "verdict": "PASS",
                "tested_sha": tested_sha,
                "total_active_ns": 123,
                "total_cycles": 4,
            }
        ),
        encoding="utf-8",
    )

    assert read_previous(summary, tested_sha) == (123, 4)

    with pytest.raises(RuntimeError, match="SHA mismatch"):
        read_previous(summary, "b" * 40)

    summary.write_text(
        json.dumps(
            {
                "verdict": "FAIL",
                "tested_sha": tested_sha,
                "total_active_ns": 123,
                "total_cycles": 4,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="not PASS"):
        read_previous(summary, tested_sha)


def test_run_stage_fails_closed_when_main_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tested_sha = "a" * 40
    executed = False

    def fake_execute_cycle(_commands: tuple[tuple[str, ...], ...]) -> tuple[int, bytes, int]:
        nonlocal executed
        executed = True
        return 0, b"unexpected", 1

    monkeypatch.setitem(run_stage.__globals__, "remote_main_sha", lambda _repository: "b" * 40)
    monkeypatch.setitem(run_stage.__globals__, "execute_cycle", fake_execute_cycle)
    args = SimpleNamespace(
        kind="aspenops",
        tested_sha=tested_sha,
        target_active_ns=10,
        stage=1,
        output_dir=tmp_path,
        previous_summary=None,
        slug="aspenops",
        repository="SUNHAOJUN22/AspenOps-Agent",
    )

    assert run_stage(args) == 3
    assert executed is False
    summary = json.loads((tmp_path / "aspenops-summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "STALE_MAIN"
    assert summary["total_active_ns"] == 0
    assert "STALE_MAIN before stage" in summary["failure"]


def test_run_stage_accumulates_only_formal_cycle_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tested_sha = "c" * 40
    cycle_ns = iter((4, 6))

    monkeypatch.setitem(run_stage.__globals__, "remote_main_sha", lambda _repository: tested_sha)
    monkeypatch.setitem(
        run_stage.__globals__,
        "execute_cycle",
        lambda _commands: (0, b"pass", next(cycle_ns)),
    )
    args = SimpleNamespace(
        kind="aspenops",
        tested_sha=tested_sha,
        target_active_ns=10,
        stage=1,
        output_dir=tmp_path,
        previous_summary=None,
        slug="aspenops",
        repository="SUNHAOJUN22/AspenOps-Agent",
    )

    assert run_stage(args) == 0
    summary = json.loads((tmp_path / "aspenops-summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "PASS"
    assert summary["stage_active_ns"] == 10
    assert summary["total_active_ns"] == 10
    assert summary["stage_cycles"] == 2
    assert summary["total_cycles"] == 2
