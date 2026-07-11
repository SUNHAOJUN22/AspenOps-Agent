"""Optional MCP server exposing narrow typed AspenOps tools."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

from aspenops.compat import discover_aspen_progids
from aspenops.models import ValueRead, ValueWrite
from aspenops.service import SessionManager

_MANAGER: SessionManager | None = None


def _manager() -> SessionManager:
    global _MANAGER
    if _MANAGER is None:
        roots_raw = os.getenv("ASPENOPS_ALLOWED_ROOTS", "")
        roots = [Path(item) for item in roots_raw.split(os.pathsep) if item]
        _MANAGER = SessionManager(allowed_roots=roots)
    return _MANAGER


def create_server() -> Any:
    try:
        module: Any = importlib.import_module("mcp.server.fastmcp")
    except ImportError as exc:
        raise RuntimeError("Install the 'agent' extra to run the MCP server") from exc

    server: Any = module.FastMCP("AspenOps Agent 1.0")

    @server.tool()  # type: ignore[untyped-decorator]
    def system_info() -> dict[str, Any]:
        """Return registered Aspen Plus Automation ProgIDs and active sessions."""
        return {
            "registered_progids": [item.__dict__ for item in discover_aspen_progids()],
            "sessions": [item.model_dump(mode="json") for item in _manager().list_sessions()],
        }

    @server.tool()  # type: ignore[untyped-decorator]
    def open_session(
        case_path: str,
        backend: str = "aspen_plus",
        visible: bool = False,
        read_only: bool = False,
        timeout_s: float = 600.0,
    ) -> dict[str, Any]:
        """Open one Aspen Plus or Mock case in an isolated spawned worker."""
        result = _manager().open_session(
            Path(case_path),
            backend=backend,
            visible=visible,
            read_only=read_only,
            timeout_s=timeout_s,
        )
        return result.model_dump(mode="json")

    @server.tool()  # type: ignore[untyped-decorator]
    def close_session(session_id: str) -> dict[str, bool]:
        """Close a session and its owned worker."""
        _manager().close_session(session_id)
        return {"closed": True}

    @server.tool()  # type: ignore[untyped-decorator]
    def get_values(session_id: str, reads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Read allowlisted semantic values in one batched IPC call."""
        parsed = [ValueRead.model_validate(item) for item in reads]
        return [item.model_dump(mode="json") for item in _manager().get_values(session_id, parsed)]

    @server.tool()  # type: ignore[untyped-decorator]
    def set_values(
        session_id: str,
        writes: list[dict[str, Any]],
        atomic: bool = True,
    ) -> list[dict[str, Any]]:
        """Validate and write allowlisted semantic values with optional rollback."""
        parsed = [ValueWrite.model_validate(item) for item in writes]
        return [
            item.model_dump(mode="json")
            for item in _manager().set_values(session_id, parsed, atomic=atomic)
        ]

    @server.tool()  # type: ignore[untyped-decorator]
    def reinitialize(session_id: str) -> dict[str, bool]:
        """Reinitialize the simulation before a new operating point."""
        _manager().reinitialize(session_id)
        return {"reinitialized": True}

    @server.tool()  # type: ignore[untyped-decorator]
    def run_simulation(session_id: str) -> dict[str, Any]:
        """Run the simulator and return convergence evidence."""
        return _manager().run(session_id).model_dump(mode="json")

    @server.tool()  # type: ignore[untyped-decorator]
    def diagnose_session(session_id: str) -> dict[str, Any]:
        """Return backend, version, status, messages and path-cache diagnostics."""
        return _manager().diagnose(session_id)

    @server.tool()  # type: ignore[untyped-decorator]
    def save_case(session_id: str, path: str | None = None) -> dict[str, bool]:
        """Save in place or to an allowlisted path."""
        _manager().save(session_id, Path(path) if path else None)
        return {"saved": True}

    return server


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
