from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus.mcp_server import AspenOpsTools, build_server


def test_mcp_surface_is_narrow_and_typed() -> None:
    async def list_names() -> list[str]:
        server = build_server(start_scheduler=False)
        tools = await server.list_tools()
        return [tool.name for tool in tools]

    names = asyncio.run(list_names())
    assert names == [
        "system_info",
        "list_semantic_variables",
        "dry_run_request",
        "run_batch_sync",
        "submit_batch",
        "submit_optimization",
        "optimization_status",
        "optimization_result",
        "cancel_optimization",
        "job_status",
        "job_result",
        "list_recent_jobs",
        "cancel_job",
        "verify_evidence_bundle",
    ]
    forbidden = {"execute_code", "call_com_method", "run_shell", "run_vba", "eval"}
    assert forbidden.isdisjoint(names)


def test_mcp_durable_submissions_pin_paths_without_mutating_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[dict[str, Any]] = []

    class FakeScheduler:
        pool_manager = SimpleNamespace(stats=lambda: {})
        store = SimpleNamespace()

        def submit(self, request: dict[str, Any]) -> str:
            submitted.append(request)
            return f"job-{len(submitted)}"

    monkeypatch.chdir(tmp_path)
    tools = AspenOpsTools(SimpleNamespace(), FakeScheduler())  # type: ignore[arg-type]
    batch = {
        "model_path": "models/case.json",
        "registry_path": "registries/nodes.json",
    }
    optimization = {
        **batch,
        "optimization": {"variables": [], "objectives": []},
    }

    assert tools.submit_batch(batch) == {"job_id": "job-1"}
    assert tools.submit_optimization(optimization) == {"job_id": "job-2"}
    assert batch["model_path"] == "models/case.json"
    for request in submitted:
        assert Path(request["model_path"]).is_absolute()
        assert Path(request["registry_path"]).is_absolute()
        assert request["metadata"]["submission_cwd"] == str(tmp_path.resolve())
