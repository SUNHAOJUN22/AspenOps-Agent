from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus import cli
from aspenops_nexus.cli import _controlled_path
from aspenops_nexus.config import Settings
from aspenops_nexus.durable_request import pin_durable_request_paths
from aspenops_nexus.policy import PolicyError


def settings(tmp_path: Path) -> Settings:
    allowed = tmp_path / "allowed"
    return Settings(
        backend="aspen_plus",
        allowed_roots=(allowed,),
        state_dir=allowed / "state",
    )


def install_settings(
    monkeypatch: pytest.MonkeyPatch,
    active: Settings,
) -> None:
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(lambda cls: active),
    )


def request_file(tmp_path: Path) -> Path:
    path = tmp_path / "request.json"
    path.write_text(json.dumps({"backend": "aspen_plus"}), encoding="utf-8")
    return path


def test_cli_output_path_must_stay_inside_allowed_roots(tmp_path: Path) -> None:
    active = settings(tmp_path)
    allowed = active.allowed_roots[0]

    assert (
        _controlled_path(allowed / "results.json", active) == (allowed / "results.json").resolve()
    )

    with pytest.raises(PolicyError, match="outside ASPENOPS_ALLOWED_ROOTS"):
        _controlled_path(tmp_path / "outside.json", active)


def test_run_batch_rejects_output_before_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = settings(tmp_path)
    install_settings(monkeypatch, active)
    called = False

    def run(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(cli, "run_batch_file", run)
    with pytest.raises(PolicyError, match="outside ASPENOPS_ALLOWED_ROOTS"):
        cli.command_run_batch(
            Namespace(
                request=str(request_file(tmp_path)),
                output=str(tmp_path / "outside.json"),
                bundle=None,
            )
        )
    assert called is False


def test_optimize_rejects_output_before_pool_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = settings(tmp_path)
    install_settings(monkeypatch, active)
    created = False

    class ForbiddenPool:
        def __init__(self, **kwargs: Any) -> None:
            nonlocal created
            created = True

    monkeypatch.setattr(cli, "PoolManager", ForbiddenPool)
    with pytest.raises(PolicyError, match="outside ASPENOPS_ALLOWED_ROOTS"):
        cli.command_optimize(
            Namespace(
                request=str(request_file(tmp_path)),
                output=str(tmp_path / "outside.json"),
            )
        )
    assert created is False


def test_certify_rejects_output_before_repeatability_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = settings(tmp_path)
    install_settings(monkeypatch, active)
    called = False

    def certify(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"passed": True}

    monkeypatch.setattr(cli, "certify_batch_document", certify)
    with pytest.raises(PolicyError, match="outside ASPENOPS_ALLOWED_ROOTS"):
        cli.command_certify(
            Namespace(
                request=str(request_file(tmp_path)),
                output=str(tmp_path / "outside.json"),
                repeats=2,
                abs_tol=1e-8,
                rel_tol=1e-6,
                workers=1,
                engineering_approved=False,
            )
        )
    assert called is False


def test_preflight_rejects_output_before_loading_the_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = settings(tmp_path)
    install_settings(monkeypatch, active)
    loaded = False

    def load(*args: Any, **kwargs: Any) -> object:
        nonlocal loaded
        loaded = True
        return object()

    monkeypatch.setattr(cli, "load_licensed_plan", load)
    with pytest.raises(PolicyError, match="outside ASPENOPS_ALLOWED_ROOTS"):
        cli.command_certification_preflight(
            Namespace(
                plan="plan.json",
                output=str(tmp_path / "outside.json"),
            )
        )
    assert loaded is False


def test_durable_request_paths_are_pinned_cross_platform(tmp_path: Path) -> None:
    submission_cwd = tmp_path / "submitter"
    normalized = pin_durable_request_paths(
        {
            "model_path": "models/case.json",
            "registry_path": "registries/nodes.json",
        },
        submission_cwd=submission_cwd,
    )

    assert Path(normalized["model_path"]).is_absolute()
    assert Path(normalized["registry_path"]).is_absolute()
    assert normalized["model_path"] == str((submission_cwd / "models/case.json").resolve())
    assert normalized["metadata"]["submission_cwd"] == str(submission_cwd.resolve())


def test_cancel_policy_clamps_negative_grace_on_windows_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = settings(tmp_path)
    install_settings(monkeypatch, active)
    calls: list[tuple[str, float]] = []
    printed: list[dict[str, Any]] = []

    class FakeStore:
        def __init__(self, path: Path) -> None:
            self.path = path

        def cancel(self, job_id: str, grace_s: float) -> bool:
            calls.append((job_id, grace_s))
            return True

        def get(self, job_id: str) -> dict[str, Any]:
            return {"job_id": job_id, "status": "cancelled"}

    monkeypatch.setattr(cli, "JobStore", FakeStore)
    monkeypatch.setattr(cli, "_json_print", printed.append)

    assert cli.command_cancel(Namespace(job_id="job-1", grace_s=-3)) == 0
    assert calls == [("job-1", 0.0)]
    assert printed[-1]["job"]["status"] == "cancelled"
