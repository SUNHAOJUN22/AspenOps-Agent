from __future__ import annotations

from pathlib import Path

import pytest

import aspenops.mcp_server as mcp_server


def reset_manager() -> None:
    if mcp_server._MANAGER is not None:
        mcp_server._MANAGER.close_all()
    mcp_server._MANAGER = None


def test_mcp_manager_requires_allowed_roots(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_manager()
    monkeypatch.delenv("ASPENOPS_ALLOWED_ROOTS", raising=False)
    monkeypatch.delenv("ASPENOPS_INSECURE_ALLOW_ANY_ROOT", raising=False)
    with pytest.raises(RuntimeError, match="ASPENOPS_ALLOWED_ROOTS"):
        mcp_server._manager()
    reset_manager()


def test_mcp_manager_enables_default_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reset_manager()
    monkeypatch.setenv("ASPENOPS_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.delenv("ASPENOPS_AUDIT_LOG", raising=False)
    manager = mcp_server._manager()
    assert manager.audit_log is not None
    assert manager.audit_log.path == tmp_path / ".aspenops" / "audit.jsonl"
    reset_manager()
