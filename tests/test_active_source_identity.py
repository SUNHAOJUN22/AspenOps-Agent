"""Local Git fixtures for runner identity, without network or solver execution."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = runpy.run_path(str(ROOT / "scripts/run_six_repository_active_gate.py"))
RUN_STAGE = NAMESPACE["run_stage"]


def git(repo: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=repo, text=True, stderr=subprocess.STDOUT
    ).strip()


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "checkout"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Local test fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "core.autocrlf", "false")
    (repo / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / ".gitignore").write_text("runtime/\n", encoding="utf-8")
    git(repo, "add", "source.py", ".gitignore")
    git(repo, "commit", "-qm", "local fixture")
    sha = git(repo, "rev-parse", "HEAD")
    monkeypatch.chdir(repo)
    monkeypatch.setitem(RUN_STAGE.__globals__, "remote_main_sha", lambda _repository: sha)
    command = (sys.executable, "-c", "print('local synthetic formal command')")
    monkeypatch.setitem(RUN_STAGE.__globals__, "COMMANDS", {"aspenops": (command,)})
    args = SimpleNamespace(
        kind="aspenops",
        tested_sha=sha,
        target_active_ns=1,
        stage=1,
        output_dir=tmp_path / "evidence",
        previous_summary=None,
        slug="fixture",
        repository="local-fixture/not-a-real-github-repository",
    )
    return repo, args, command


def summary(args: SimpleNamespace) -> dict[str, Any]:
    return json.loads((args.output_dir / "fixture-summary.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("output_location", ["external", "ignored"])
def test_clean_checkout_and_ignored_runtime_outputs_remain_supported(checkout, output_location):
    repo, args, _ = checkout
    if output_location == "ignored":
        args.output_dir = repo / "runtime"
    assert RUN_STAGE(args) == 0
    report = summary(args)
    assert report["verdict"] == "PASS"
    assert report["source_identity"] == {
        "head": args.tested_sha,
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "repository_root": str(repo.resolve()),
    }
    assert report["stage_cycles"] == 1
    assert report["stage_active_ns"] > 0


@pytest.mark.parametrize(
    "state", ["wrong_head", "dirty", "staged", "untracked", "nested", "nongit"]
)
def test_mismatched_local_checkout_is_rejected_before_formal_commands(checkout, monkeypatch, state):
    repo, args, _ = checkout
    if state in {"wrong_head", "dirty", "staged"}:
        (repo / "source.py").write_text("VALUE = 2\n", encoding="utf-8")
        if state in {"wrong_head", "staged"}:
            git(repo, "add", "source.py")
        if state == "wrong_head":
            git(repo, "commit", "-qm", "different fixture source")
    elif state == "untracked":
        (repo / "extra_test.py").write_text("VALUE = 2\n", encoding="utf-8")
    else:
        cwd = (repo if state == "nested" else repo.parent) / state
        cwd.mkdir()
        monkeypatch.chdir(cwd)
    calls = []
    monkeypatch.setitem(
        RUN_STAGE.__globals__, "execute_cycle", lambda _commands: calls.append(True)
    )
    assert RUN_STAGE(args) == 3
    assert calls == []
    report = summary(args)
    assert report["verdict"] == "SOURCE_MISMATCH"
    assert report["total_active_ns"] == report["total_cycles"] == 0


@pytest.mark.parametrize("path", ["source.py", "new_test.py"])
def test_source_mutation_during_successful_command_cannot_produce_pass(checkout, monkeypatch, path):
    _, args, _ = checkout
    command = (
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({path!r}).write_text('VALUE = 3\\n')",
    )
    monkeypatch.setitem(RUN_STAGE.__globals__, "COMMANDS", {"aspenops": (command,)})
    assert RUN_STAGE(args) == 3
    report = summary(args)
    assert report["verdict"] == "SOURCE_MISMATCH"
    assert "after cycle 1" in report["failure"]
    assert report["stage_cycles"] == 1
    assert report["stage_active_ns"] > 0


def test_final_local_check_rejects_a_change_after_last_cycle(checkout, monkeypatch):
    repo, args, _ = checkout
    calls = 0

    def remote_sha(_repository):
        nonlocal calls
        calls += 1
        if calls == 3:
            (repo / "source.py").write_text("VALUE = 4\n", encoding="utf-8")
        return args.tested_sha

    monkeypatch.setitem(RUN_STAGE.__globals__, "remote_main_sha", remote_sha)
    assert RUN_STAGE(args) == 3
    report = summary(args)
    assert report["verdict"] == "SOURCE_MISMATCH"
    assert "at stage completion" in report["failure"]


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_index_flags_cannot_hide_changed_source_from_identity_checks(checkout, monkeypatch, flag):
    repo, args, _ = checkout
    git(repo, "update-index", flag, "source.py")
    (repo / "source.py").write_text("VALUE = 5\n", encoding="utf-8")
    assert git(repo, "status", "--porcelain") == ""
    calls = []
    monkeypatch.setitem(
        RUN_STAGE.__globals__, "execute_cycle", lambda _commands: calls.append(True)
    )
    assert RUN_STAGE(args) == 3
    assert calls == []
    assert "index flags" in summary(args)["failure"]


def test_valid_stage_continuation_carries_only_the_matching_prior_total(checkout):
    _, args, _ = checkout
    assert RUN_STAGE(args) == 0
    first = summary(args)
    prior = args.output_dir / "fixture-summary.json"
    args.stage = 2
    args.target_active_ns = first["total_active_ns"] + 1
    args.previous_summary = prior
    args.output_dir = args.output_dir.parent / "stage-two-evidence"
    assert RUN_STAGE(args) == 0
    second = summary(args)
    assert second["initial_active_ns"] == first["total_active_ns"]
    assert second["initial_cycles"] == first["total_cycles"]
    assert second["total_active_ns"] == first["total_active_ns"] + second["stage_active_ns"]
    assert second["total_cycles"] == first["total_cycles"] + second["stage_cycles"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("repository", "different/repository"),
        ("kind", "dft"),
        ("slug", "different"),
        ("command_identity", "a" * 64),
        ("commands", [["python", "different_gate.py"]]),
        ("stage", 99),
        ("total_cycles", 99),
        ("total_active_ns", 1),
        ("target_active_ns", 999),
        ("schema_version", "six-repository-active-gate/v4"),
        ("source_identity", {"head": "a" * 40, "tree": "b" * 40}),
    ],
)
def test_prior_stage_identity_and_completion_mismatches_block_execution(
    checkout, monkeypatch, field, value
):
    repo, args, command = checkout
    prior = {
        "schema_version": "six-repository-active-gate/v5",
        "verdict": "PASS",
        "tested_sha": args.tested_sha,
        "repository": args.repository,
        "kind": args.kind,
        "slug": args.slug,
        "command_identity": NAMESPACE["command_identity"]((command,)),
        "commands": [list(command)],
        "source_identity": {"head": args.tested_sha, "tree": git(repo, "rev-parse", "HEAD^{tree}")},
        "stage": 1,
        "target_active_ns": 10,
        "initial_active_ns": 0,
        "initial_cycles": 0,
        "stage_active_ns": 12,
        "stage_cycles": 1,
        "total_active_ns": 12,
        "total_cycles": 1,
        "failure": None,
    }
    prior[field] = value
    args.previous_summary = repo.parent / "prior-summary.json"
    args.previous_summary.write_text(json.dumps(prior), encoding="utf-8")
    args.stage = 2
    args.target_active_ns = 20
    calls = []
    monkeypatch.setitem(
        RUN_STAGE.__globals__, "execute_cycle", lambda _commands: calls.append(True)
    )
    assert RUN_STAGE(args) == 2
    assert calls == []
    assert summary(args)["verdict"] == "INVALID_PREVIOUS_STAGE"


def test_a_later_stage_requires_the_prior_receipt(checkout):
    _, args, _ = checkout
    args.stage = 2
    assert RUN_STAGE(args) == 2
    assert summary(args)["verdict"] == "INVALID_PREVIOUS_STAGE"
