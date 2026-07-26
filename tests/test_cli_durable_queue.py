from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus import cli


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        state_dir=tmp_path / "state",
        job_max_attempts=3,
    )


def _install_settings(
    monkeypatch: pytest.MonkeyPatch,
    settings: SimpleNamespace,
) -> None:
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(lambda cls: settings),
    )


def test_durable_request_paths_are_pinned_to_submission_directory(tmp_path: Path) -> None:
    submission_cwd = tmp_path / "submitter"
    absolute_model = tmp_path / "absolute" / "case.json"
    request = {
        "model_path": "models/case.json",
        "registry_path": "registries/nodes.json",
        "metadata": {"case": "portable"},
    }

    normalized = cli._normalize_durable_request(
        request,
        submission_cwd=submission_cwd,
    )

    assert normalized["model_path"] == str((submission_cwd / "models/case.json").resolve())
    assert normalized["registry_path"] == str(
        (submission_cwd / "registries/nodes.json").resolve()
    )
    assert normalized["metadata"] == {
        "case": "portable",
        "submission_cwd": str(submission_cwd.resolve()),
    }
    assert request["model_path"] == "models/case.json"

    absolute = cli._normalize_durable_request(
        {"model_path": str(absolute_model)},
        submission_cwd=submission_cwd,
    )
    assert absolute["model_path"] == str(absolute_model.resolve())


def test_submit_persists_pinned_paths_and_reports_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    _install_settings(monkeypatch, settings)
    submission_cwd = tmp_path / "submitter"
    submission_cwd.mkdir()
    monkeypatch.chdir(submission_cwd)

    request_path = submission_cwd / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "backend": "mock",
                "model_path": "models/case.json",
                "registry_path": "registries/nodes.json",
            }
        ),
        encoding="utf-8",
    )

    validated: list[dict[str, Any]] = []
    persisted: list[dict[str, Any]] = []
    printed: list[dict[str, Any]] = []
    monkeypatch.setattr(
        cli,
        "_validate_scheduled_request",
        lambda request, active: validated.append(request),
    )
    monkeypatch.setattr(cli, "_json_print", printed.append)

    class FakeStore:
        def __init__(self, path: Path) -> None:
            self.path = path

        def create(self, request: dict[str, Any], max_attempts: int) -> str:
            assert max_attempts == 3
            persisted.append(request)
            return "job-123"

    monkeypatch.setattr(cli, "JobStore", FakeStore)

    assert cli.command_submit(Namespace(request=str(request_path))) == 0
    assert validated == persisted
    assert persisted[0]["model_path"] == str(
        (submission_cwd / "models/case.json").resolve()
    )
    assert persisted[0]["registry_path"] == str(
        (submission_cwd / "registries/nodes.json").resolve()
    )
    assert printed[-1]["paths_pinned"] is True
    assert printed[-1]["submission_cwd"] == str(submission_cwd.resolve())


@pytest.mark.parametrize(
    ("accepted", "expected"),
    [(True, 0), (False, 2)],
)
def test_cancel_command_clamps_grace_and_reports_current_record(
    accepted: bool,
    expected: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    _install_settings(monkeypatch, settings)
    printed: list[dict[str, Any]] = []
    calls: list[tuple[str, float]] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    class FakeStore:
        def __init__(self, path: Path) -> None:
            self.path = path

        def cancel(self, job_id: str, grace_s: float) -> bool:
            calls.append((job_id, grace_s))
            return accepted

        def get(self, job_id: str) -> dict[str, Any] | None:
            return {"job_id": job_id, "status": "cancelled"} if accepted else None

    monkeypatch.setattr(cli, "JobStore", FakeStore)

    result = cli.command_cancel(Namespace(job_id="job-1", grace_s=-5))
    assert result == expected
    assert calls == [("job-1", 0.0)]
    assert printed[-1]["accepted"] is accepted


def test_parser_exposes_cancel_and_preserves_integer_certification_repeats() -> None:
    parser = cli.build_parser()
    cancel = parser.parse_args(["cancel", "job-1", "--grace-s", "1.5"])
    certify = parser.parse_args(["certify", "request.json", "--repeats", "4"])

    assert cancel.command == "cancel"
    assert cancel.grace_s == 1.5
    assert certify.repeats == 4
    assert isinstance(certify.repeats, int)
