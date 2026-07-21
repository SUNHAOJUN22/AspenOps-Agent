from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus import cli


def use_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> SimpleNamespace:
    active = SimpleNamespace(state_dir=tmp_path / "state")
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(lambda cls: active),
    )
    return active


@pytest.mark.parametrize(("ready", "expected"), [(True, 0), (False, 2)])
def test_certification_preflight_command_writes_machine_readable_report(
    ready: bool,
    expected: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = use_settings(monkeypatch, tmp_path)
    plan = object()
    monkeypatch.setattr(cli, "load_licensed_plan", lambda path: plan)
    monkeypatch.setattr(
        cli,
        "certification_preflight",
        lambda selected, settings: {
            "schema": "aspenops.licensed-certification-preflight/v1",
            "ready": ready,
            "blockers": [] if ready else [{"code": "blocked"}],
        },
    )
    printed: list[dict[str, Any]] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)
    output = tmp_path / "reports" / "preflight.json"

    result = cli.command_certification_preflight(
        Namespace(plan="plan.json", output=str(output))
    )

    assert result == expected
    assert json.loads(output.read_text(encoding="utf-8"))["ready"] is ready
    assert printed[-1]["preflight_path"] == str(output.resolve())
    assert active.state_dir == tmp_path / "state"


@pytest.mark.parametrize(
    ("runtime_gate", "bundle_ok", "expected"),
    [(True, True, 0), (False, True, 2), (True, False, 2)],
)
def test_certify_licensed_command_never_maps_pending_status_to_success_by_itself(
    runtime_gate: bool,
    bundle_ok: bool,
    expected: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = use_settings(monkeypatch, tmp_path)
    plan = object()
    monkeypatch.setattr(cli, "load_licensed_plan", lambda path: plan)
    captured: dict[str, Any] = {}

    def execute(
        selected: object,
        settings: object,
        *,
        output_dir: Path,
    ) -> dict[str, Any]:
        captured.update(plan=selected, settings=settings, output_dir=output_dir)
        return {
            "runtime_gate_passed": runtime_gate,
            "certification_status": "PENDING_REAL_ASPEN_CERTIFICATION",
            "bundle_verification": {"ok": bundle_ok},
        }

    monkeypatch.setattr(cli, "execute_licensed_certification", execute)
    printed: list[dict[str, Any]] = []
    monkeypatch.setattr(cli, "_json_print", printed.append)

    result = cli.command_certify_licensed(
        Namespace(plan="plan.json", output_dir=None)
    )

    assert result == expected
    assert captured["plan"] is plan
    assert captured["settings"] is active
    assert captured["output_dir"] == active.state_dir / "licensed-certification"
    assert printed[-1]["certification_status"] == "PENDING_REAL_ASPEN_CERTIFICATION"


@pytest.mark.parametrize(("valid", "expected"), [(True, 0), (False, 2)])
def test_verify_licensed_bundle_command_uses_explicit_trusted_key(
    valid: bool,
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def verify(bundle: str, *, trusted_public_key: str) -> dict[str, Any]:
        captured.update(bundle=bundle, trusted_public_key=trusted_public_key)
        return {"ok": valid, "verification_status": "signed-valid" if valid else "signed-invalid"}

    monkeypatch.setattr(cli, "verify_licensed_certification_bundle", verify)
    monkeypatch.setattr(cli, "_json_print", lambda value: None)

    result = cli.command_verify_licensed_bundle(
        Namespace(bundle="bundle.zip", public_key="trusted-public.pem")
    )

    assert result == expected
    assert captured == {
        "bundle": "bundle.zip",
        "trusted_public_key": "trusted-public.pem",
    }


def test_parser_exposes_licensed_commands_and_repeatability_boundary() -> None:
    parser = cli.build_parser()

    repeatability = parser.parse_args(
        [
            "certify",
            "request.json",
            "--workers",
            "4",
            "--engineering-approved",
        ]
    )
    preflight = parser.parse_args(
        ["certification-preflight", "plan.json", "--output", "preflight.json"]
    )
    execute = parser.parse_args(
        ["certify-licensed", "plan.json", "--output-dir", "certification"]
    )
    verify = parser.parse_args(
        [
            "verify-licensed-bundle",
            "bundle.zip",
            "--public-key",
            "trusted-public.pem",
        ]
    )

    assert repeatability.command == "certify"
    assert repeatability.workers == 4
    assert repeatability.engineering_approved is True
    assert preflight.func is cli.command_certification_preflight
    assert execute.func is cli.command_certify_licensed
    assert verify.func is cli.command_verify_licensed_bundle
