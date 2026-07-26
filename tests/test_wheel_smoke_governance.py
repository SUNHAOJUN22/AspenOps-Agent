from __future__ import annotations

import asyncio
import tomllib
from pathlib import Path

import aspenops_nexus.mcp_server as mcp_server


def test_wheel_smoke_uses_hashed_locked_runtime_dependencies() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    export_block = text[
        text.index("uv export --frozen") : text.index("uv venv --python 3.12")
    ]

    assert "--extra agent" in export_block
    assert "--no-default-groups" in export_block
    assert "--no-emit-project" in export_block
    assert "--format requirements.txt" in export_block
    assert "--output-file var/ci/runtime-requirements.txt" in export_block
    assert "uv pip sync" in text
    assert "--require-hashes" in text
    assert "uv pip install" in text
    assert "--offline" in text
    assert "--no-deps" in text
    assert "uv pip check --python /tmp/aspenops-wheel/bin/python" in text
    assert "/tmp/aspenops-wheel/bin/aspenops scheduler --help" in text
    assert "/tmp/aspenops-wheel/bin/aspenops cancel --help" in text
    assert "/tmp/aspenops-wheel/bin/aspenops optimize --help" in text
    assert "_require_supported_mcp_sdk" in text
    assert "wheel-mcp-version.log" in text
    assert "tests/test_cli_durable_queue.py" in text
    assert "uv run aspenops submit examples/batch-request.example.json" in text
    assert 'data["paths_pinned"] is True' in text
    assert "uv run aspenops cancel \"$job_id\" --grace-s 0" in text
    assert "uv run aspenops optimize examples/optimization-request.example.json" in text
    assert "/tmp/aspenops-wheel/bin/pip install dist/*.whl" not in text

    assert text.index("- name: Build distributions") < text.index("- name: Verify MCP surface")
    checker = Path("scripts/check_mcp.py").read_text(encoding="utf-8")
    assert "inspect_wheel" in checker
    assert 'Path("dist")' in checker
    assert "if dist_dir.exists():" in checker
    assert '"wheel_metadata": wheel_metadata' in checker


def test_mcp_runtime_lock_package_and_docs_remain_compatible() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    agent_requirements = project["project"]["optional-dependencies"]["agent"]
    assert agent_requirements == ["mcp>=1.9,<2"]

    lock = tomllib.loads(Path("uv.lock").read_text(encoding="utf-8"))
    packages = lock.get("package", [])
    versions = [str(package["version"]) for package in packages if package.get("name") == "mcp"]
    assert versions == ["1.28.1"]
    assert mcp_server._require_supported_mcp_sdk() == "1.28.1"

    major, minor, patch = (int(part) for part in versions[0].split("."))
    assert major == mcp_server.SUPPORTED_MCP_MAJOR == 1
    assert (major, minor, patch) >= (1, 9, 0)

    server = Path("src/aspenops_nexus/mcp_server.py").read_text(encoding="utf-8")
    assert 'SUPPORTED_MCP_MAJOR = 1' in server
    assert 'MCP_INSTALL_CONSTRAINT = "mcp>=1.9,<2"' in server
    assert "_require_supported_mcp_sdk" in server
    assert "_scheduler_lifespan" in server

    for readme in (Path("README.md"), Path("README.en.md")):
        text = readme.read_text(encoding="utf-8")
        assert "mcp>=1.9,<2" in text
        assert "mcp-runtime-lifecycle.svg" in text


def test_mcp_lifespan_starts_and_stops_the_owned_scheduler() -> None:
    events: list[str] = []

    class FakeScheduler:
        def start(self) -> None:
            events.append("start")

        def stop(self) -> None:
            events.append("stop")

    async def exercise() -> None:
        async with mcp_server._scheduler_lifespan(
            None,
            scheduler=FakeScheduler(),  # type: ignore[arg-type]
            start_scheduler=True,
        ):
            events.append("serve")

    asyncio.run(exercise())
    assert events == ["start", "serve", "stop"]
