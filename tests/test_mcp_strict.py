from importlib.resources import as_file, files
from pathlib import Path

import pytest

import aspenops_nexus.mcp_server as mcp_server


def resource(name: str) -> Path:
    with as_file(files("aspenops_nexus.data").joinpath(name)) as path:
        return Path(path)


def request() -> dict:
    return {
        "backend": "mock",
        "model_path": str(resource("mock-case.json")),
        "registry_path": str(resource("node-registry.json")),
        "points": [{}],
        "reads": [],
        "timeout_s": 5,
    }


@pytest.fixture(autouse=True)
def reset_scheduler() -> None:
    mcp_server._stop_scheduler()
    yield
    mcp_server._stop_scheduler()


def configure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str = "default") -> None:
    monkeypatch.setenv("ASPENOPS_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("ASPENOPS_MODE", mode)
    monkeypatch.setenv("ASPENOPS_LICENSE_SLOTS", "1")
    monkeypatch.setenv("ASPENOPS_MAX_WORKERS", "1")
    monkeypatch.delenv("ASPENOPS_ALLOWED_ROOTS", raising=False)


def test_module_import_and_job_reads_do_not_start_scheduler(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure(monkeypatch, tmp_path)
    assert mcp_server._scheduler is None
    result = mcp_server.get_job("bad")
    assert result["ok"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert mcp_server._scheduler is None


def test_invalid_idempotency_key_fails_before_scheduler_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure(monkeypatch, tmp_path)
    result = mcp_server.submit_batch(request(), idempotency_key="contains spaces")
    assert result["ok"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert mcp_server._scheduler is None


def test_dry_run_uses_strict_request_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure(monkeypatch, tmp_path)
    result = mcp_server.dry_run({**request(), "reinitialize": "false"})
    assert result["ok"] is False
    assert result["error"]["code"] == "UNCLASSIFIED_ERROR"
    assert result["error"]["retryable"] is False


def test_describe_registry_enforces_allowed_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    configure(monkeypatch, tmp_path)
    monkeypatch.setenv("ASPENOPS_ALLOWED_ROOTS", str(state))
    result = mcp_server.describe_registry(str(resource("node-registry.json")))
    assert result["ok"] is False
    assert result["error"]["code"] == "AUTHORIZATION_ERROR"


def test_cache_clear_requires_enhanced_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure(monkeypatch, tmp_path, mode="default")
    denied = mcp_server.cache_clear()
    assert denied["ok"] is False
    assert denied["error"]["code"] == "AUTHORIZATION_ERROR"

    configure(monkeypatch, tmp_path, mode="enhanced")
    allowed = mcp_server.cache_clear()
    assert allowed == {"ok": True, "removed": 0}
    assert mcp_server._scheduler is None


def test_cache_stats_does_not_start_scheduler(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure(monkeypatch, tmp_path)
    result = mcp_server.cache_stats()
    assert result["ok"] is True
    assert result["entries"] == 0
    assert mcp_server._scheduler is None
