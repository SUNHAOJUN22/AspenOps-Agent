from pathlib import Path

import pytest

from aspenops.audit import AuditLog
from aspenops.errors import (
    AccessViolation,
    ConfigurationError,
    SessionDeadError,
    WorkerTimeout,
)
from aspenops.models import RunState, SessionState, ValueRead, ValueWrite
from aspenops.service import SessionManager


def test_session_manager_and_audit(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    audit = AuditLog(tmp_path / "audit.jsonl")
    manager = SessionManager(allowed_roots=[tmp_path], audit_log=audit, default_timeout_s=10)
    session = manager.open_session(case, backend="mock")
    manager.set_values(
        session.session_id,
        [
            ValueWrite(
                key="stream.input.temperature",
                identifiers={"stream": "FEED"},
                value=100,
                unit="C",
            )
        ],
    )
    assert manager.run(session.session_id).state == RunState.CONVERGED
    values = manager.get_values(
        session.session_id,
        [ValueRead(key="stream.output.temperature", identifiers={"stream": "PRODUCT"})],
    )
    assert float(values[0].value) > 100
    listed = manager.list_sessions()[0]
    assert listed.alive
    assert listed.state == SessionState.OPEN
    manager.close_all()
    assert audit.path.read_text(encoding="utf-8").count("\n") >= 4


def test_path_policy_and_unknown_session(tmp_path: Path) -> None:
    manager = SessionManager(allowed_roots=[tmp_path / "allowed"])
    with pytest.raises(AccessViolation):
        manager.open_session(tmp_path / "outside.json", backend="mock")
    with pytest.raises(ConfigurationError):
        manager.run("missing")


def test_service_save_diagnose_and_close(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    manager = SessionManager(allowed_roots=[tmp_path], default_timeout_s=10)
    session = manager.open_session(case, backend="mock")
    assert manager.diagnose(session.session_id)["backend"] == "mock"
    saved = tmp_path / "saved.json"
    manager.save(session.session_id, saved)
    assert saved.exists()
    manager.close_session(session.session_id)
    assert manager.list_sessions() == []
    missing = tmp_path / "missing.bkp"
    with pytest.raises(ConfigurationError):
        manager.open_session(missing, backend="aspen_plus")


def test_read_only_session_rejects_writes_and_saves(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    manager = SessionManager(allowed_roots=[tmp_path], default_timeout_s=10)
    session = manager.open_session(case, backend="mock", read_only=True)
    assert session.read_only
    with pytest.raises(AccessViolation, match="Read-only"):
        manager.set_values(
            session.session_id,
            [
                ValueWrite(
                    key="stream.input.temperature",
                    identifiers={"stream": "FEED"},
                    value=90,
                    unit="C",
                )
            ],
        )
    with pytest.raises(AccessViolation, match="Read-only"):
        manager.save(session.session_id)
    manager.close_all()


def test_dead_session_requires_explicit_recovery(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    manager = SessionManager(allowed_roots=[tmp_path], default_timeout_s=0.05)
    session = manager.open_session(
        case,
        backend="mock",
        backend_options={"run_delay_s": 0.3},
    )
    with pytest.raises(WorkerTimeout):
        manager.run(session.session_id)
    listed = manager.list_sessions()[0]
    assert listed.state == SessionState.DEAD
    assert not listed.alive
    with pytest.raises(SessionDeadError):
        manager.diagnose(session.session_id)
    recovered = manager.recover_session(session.session_id)
    assert recovered.state == SessionState.OPEN
    assert recovered.alive
    assert manager.diagnose(session.session_id)["opened"] is True
    manager.close_all()
