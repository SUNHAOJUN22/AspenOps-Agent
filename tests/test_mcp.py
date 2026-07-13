import asyncio

import pytest

from aspenops.errors import ConfigurationError
from aspenops.mcp_server import _build_manager_from_env, create_server


def test_mcp_server_registers_narrow_tool_surface() -> None:
    server = create_server()
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "system_info",
        "open_session",
        "recover_session",
        "close_session",
        "get_values",
        "set_values",
        "reinitialize",
        "run_simulation",
        "diagnose_session",
        "save_case",
    }


def test_mcp_configuration_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASPENOPS_ALLOWED_ROOTS", raising=False)
    monkeypatch.delenv("ASPENOPS_AUDIT_LOG", raising=False)
    monkeypatch.delenv("ASPENOPS_INSECURE_LOCAL_DEV", raising=False)
    with pytest.raises(ConfigurationError, match="ASPENOPS_ALLOWED_ROOTS"):
        _build_manager_from_env()


def test_mcp_configuration_requires_audit(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("ASPENOPS_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.delenv("ASPENOPS_AUDIT_LOG", raising=False)
    monkeypatch.delenv("ASPENOPS_INSECURE_LOCAL_DEV", raising=False)
    with pytest.raises(ConfigurationError, match="ASPENOPS_AUDIT_LOG"):
        _build_manager_from_env()


def test_mcp_secure_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    audit_path = tmp_path / "audit" / "aspenops.jsonl"
    monkeypatch.setenv("ASPENOPS_ALLOWED_ROOTS", str(tmp_path))
    monkeypatch.setenv("ASPENOPS_AUDIT_LOG", str(audit_path))
    monkeypatch.delenv("ASPENOPS_INSECURE_LOCAL_DEV", raising=False)
    manager = _build_manager_from_env()
    assert manager.allowed_roots == [tmp_path.resolve()]
    assert manager.audit_log is not None
    assert manager.audit_log.path == audit_path.resolve()


def test_mcp_insecure_local_dev_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASPENOPS_ALLOWED_ROOTS", raising=False)
    monkeypatch.delenv("ASPENOPS_AUDIT_LOG", raising=False)
    monkeypatch.setenv("ASPENOPS_INSECURE_LOCAL_DEV", "1")
    manager = _build_manager_from_env()
    assert manager.allowed_roots == []
    assert manager.audit_log is None
