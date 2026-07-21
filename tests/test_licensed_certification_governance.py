from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from aspenops_nexus.licensed_certification import (
    LicensedCertificationPlan,
    certification_preflight,
)
from aspenops_nexus.mcp_server import build_server
from aspenops_nexus.config import Settings


def test_example_plan_parses_but_cannot_pass_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    example = Path("examples/licensed-certification-plan.example.json")
    plan = LicensedCertificationPlan.from_document(
        __import__("json").loads(example.read_text(encoding="utf-8"))
    )
    monkeypatch.setattr(
        "aspenops_nexus.licensed_certification.compatibility_report",
        lambda: {"aspen_plus": []},
    )
    settings = Settings(
        backend="aspen_plus",
        state_dir=tmp_path / "state",
        allowed_roots=(tmp_path.resolve(),),
        license_slots=1,
    )

    report = certification_preflight(
        plan,
        settings,
        environment={
            "GITHUB_SHA": "f" * 40,
            "RUNNER_NAME": "unapproved-runner",
            "RUNNER_ARCH": "X64",
            "RUNNER_ENVIRONMENT": "self-hosted",
            "ASPENOPS_LICENSE_SERVER_IDENTITY": "wrong-server",
            "ASPENOPS_LICENSE_FEATURES": "wrong-feature",
        },
        system_name="Windows",
        machine_architecture="X64",
        pointer_bits=64,
    )

    assert report["ready"] is False
    codes = {item["code"] for item in report["blockers"]}
    assert "commit_mismatch" in codes
    assert "engineering_acceptance_pending" in codes
    assert "model_missing" in codes
    assert "registry_missing" in codes
    assert "approved_progid_missing" in codes
    assert "signing_key_missing" in codes


def test_mcp_never_exposes_licensed_certification_or_real_execution() -> None:
    async def tool_names() -> set[str]:
        server = build_server()
        tools = await server.list_tools()
        return {tool.name for tool in tools}

    names = asyncio.run(tool_names())
    prohibited = {
        "certify_licensed",
        "licensed_certification",
        "certification_preflight",
        "verify_licensed_bundle",
        "run_real_aspen",
    }

    assert prohibited.isdisjoint(names)
    assert len(names) == 14
