"""Session service exposed to CLI and MCP clients."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aspenops.audit import AuditLog
from aspenops.errors import (
    AccessViolation,
    ConfigurationError,
    SessionDeadError,
    WorkerError,
)
from aspenops.models import (
    RunReport,
    SessionInfo,
    SessionState,
    ValueRead,
    ValueResult,
    ValueWrite,
)
from aspenops.worker import WorkerClient


@dataclass
class _SessionRecord:
    client: WorkerClient
    backend: str
    path: Path
    visible: bool
    read_only: bool
    backend_options: dict[str, Any]
    timeout_s: float
    state: SessionState = SessionState.OPEN


class SessionManager:
    def __init__(
        self,
        *,
        allowed_roots: list[Path] | None = None,
        audit_log: AuditLog | None = None,
        default_timeout_s: float = 120.0,
    ) -> None:
        if default_timeout_s <= 0:
            raise ConfigurationError("default_timeout_s must be positive")
        self.allowed_roots = [root.resolve() for root in allowed_roots or []]
        self.audit_log = audit_log
        self.default_timeout_s = default_timeout_s
        self._sessions: dict[str, _SessionRecord] = {}
        self._lock = threading.RLock()

    def open_session(
        self,
        case_path: Path,
        *,
        backend: str = "aspen_plus",
        visible: bool = False,
        read_only: bool = False,
        backend_options: dict[str, Any] | None = None,
        timeout_s: float | None = None,
    ) -> SessionInfo:
        resolved = case_path.resolve()
        self._check_path(resolved)
        if backend == "aspen_plus" and not resolved.exists():
            raise ConfigurationError(f"Aspen case not found: {resolved}")
        effective_timeout = self.default_timeout_s if timeout_s is None else timeout_s
        if effective_timeout <= 0:
            raise ConfigurationError("timeout_s must be positive")
        options = dict(backend_options or {})
        client = WorkerClient(
            backend,
            timeout_s=effective_timeout,
            backend_options=options,
        )
        client.start()
        try:
            client.call(
                "open",
                {"path": str(resolved), "visible": visible, "read_only": read_only},
            )
        except Exception:
            client.shutdown()
            raise
        session_id = uuid.uuid4().hex
        record = _SessionRecord(
            client=client,
            backend=backend,
            path=resolved,
            visible=visible,
            read_only=read_only,
            backend_options=options,
            timeout_s=effective_timeout,
        )
        with self._lock:
            self._sessions[session_id] = record
        self._audit(
            "session.open",
            {
                "session_id": session_id,
                "backend": backend,
                "path": str(resolved),
                "read_only": read_only,
            },
        )
        return self._session_info(session_id, record)

    def recover_session(self, session_id: str) -> SessionInfo:
        """Explicitly replace a dead worker and reopen its original case.

        Recovery restores the case from its configured path. Unsaved in-memory
        changes from the terminated process cannot be recovered and are never
        implied to have survived.
        """
        with self._lock:
            record = self._record(session_id)
            if record.state == SessionState.OPEN and record.client.alive:
                return self._session_info(session_id, record)
            old_client = record.client
            record.state = SessionState.DEAD
        old_client.shutdown()
        replacement = WorkerClient(
            record.backend,
            timeout_s=record.timeout_s,
            backend_options=record.backend_options,
        )
        try:
            replacement.start()
            replacement.call(
                "open",
                {
                    "path": str(record.path),
                    "visible": record.visible,
                    "read_only": record.read_only,
                },
            )
        except Exception:
            replacement.shutdown()
            self._audit("session.recovery_failed", {"session_id": session_id})
            raise
        with self._lock:
            record.client = replacement
            record.state = SessionState.OPEN
        self._audit(
            "session.recovered",
            {
                "session_id": session_id,
                "path": str(record.path),
                "unsaved_state_restored": False,
            },
        )
        return self._session_info(session_id, record)

    def close_session(self, session_id: str) -> None:
        with self._lock:
            try:
                record = self._sessions.pop(session_id)
            except KeyError as exc:
                raise ConfigurationError(f"Unknown session: {session_id}") from exc
            record.state = SessionState.CLOSED
        record.client.shutdown()
        self._audit("session.close", {"session_id": session_id})

    def get_values(self, session_id: str, reads: list[ValueRead]) -> list[ValueResult]:
        payload = {"reads": [read.model_dump(mode="json") for read in reads]}
        raw = self._call(session_id, "get_many", payload)
        results = [ValueResult.model_validate(item) for item in raw]
        self._audit("values.read", {"session_id": session_id, "count": len(results)})
        return results

    def set_values(
        self,
        session_id: str,
        writes: list[ValueWrite],
        *,
        atomic: bool = True,
    ) -> list[ValueResult]:
        record = self._record(session_id)
        if record.read_only:
            raise AccessViolation("Read-only session cannot modify simulator values")
        payload = {
            "writes": [write.model_dump(mode="json") for write in writes],
            "atomic": atomic,
        }
        raw = self._call(session_id, "set_many", payload)
        results = [ValueResult.model_validate(item) for item in raw]
        self._audit(
            "values.write", {"session_id": session_id, "count": len(results), "atomic": atomic}
        )
        return results

    def run(self, session_id: str) -> RunReport:
        report = RunReport.model_validate(self._call(session_id, "run"))
        self._audit("simulation.run", {"session_id": session_id, "state": report.state.value})
        return report

    def reinitialize(self, session_id: str) -> None:
        self._call(session_id, "reinitialize")
        self._audit("simulation.reinitialize", {"session_id": session_id})

    def save(self, session_id: str, path: Path | None = None) -> None:
        record = self._record(session_id)
        if record.read_only:
            raise AccessViolation("Read-only session cannot save a simulator case")
        if path is not None:
            resolved = path.resolve()
            self._check_path(resolved)
        else:
            resolved = None
        self._call(session_id, "save", {"path": str(resolved) if resolved else None})
        self._audit(
            "simulation.save",
            {"session_id": session_id, "path": str(resolved) if resolved else None},
        )

    def diagnose(self, session_id: str) -> dict[str, Any]:
        result = self._call(session_id, "diagnose")
        if not isinstance(result, dict):
            raise TypeError("Diagnosis must be a mapping")
        return result

    def list_sessions(self) -> list[SessionInfo]:
        with self._lock:
            for record in self._sessions.values():
                if record.state == SessionState.OPEN and not record.client.alive:
                    record.state = SessionState.DEAD
            return [
                self._session_info(session_id, record)
                for session_id, record in self._sessions.items()
            ]

    def close_all(self) -> None:
        with self._lock:
            identifiers = list(self._sessions)
        for session_id in identifiers:
            self.close_session(session_id)

    def _call(
        self,
        session_id: str,
        operation: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        record = self._record(session_id)
        self._require_open(session_id, record)
        try:
            return record.client.call(operation, payload)
        except WorkerError:
            if not record.client.alive:
                self._mark_dead(session_id, operation)
            raise

    def _record(self, session_id: str) -> _SessionRecord:
        with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError as exc:
                raise ConfigurationError(f"Unknown session: {session_id}") from exc

    def _require_open(self, session_id: str, record: _SessionRecord) -> None:
        if record.state != SessionState.OPEN or not record.client.alive:
            if record.state != SessionState.CLOSED:
                record.state = SessionState.DEAD
            raise SessionDeadError(
                f"Session {session_id} is not operational; call recover_session explicitly"
            )

    def _mark_dead(self, session_id: str, operation: str) -> None:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is not None and record.state != SessionState.CLOSED:
                record.state = SessionState.DEAD
        self._audit("session.dead", {"session_id": session_id, "operation": operation})

    @staticmethod
    def _session_info(session_id: str, record: _SessionRecord) -> SessionInfo:
        alive = record.state == SessionState.OPEN and record.client.alive
        return SessionInfo(
            session_id=session_id,
            backend=record.backend,
            case_path=str(record.path),
            alive=alive,
            state=record.state,
            read_only=record.read_only,
        )

    def _check_path(self, path: Path) -> None:
        if not self.allowed_roots:
            return
        if not any(path == root or root in path.parents for root in self.allowed_roots):
            raise AccessViolation(f"Path is outside allowed roots: {path}")

    def _audit(self, event: str, payload: dict[str, Any]) -> None:
        if self.audit_log is not None:
            self.audit_log.write(event, payload)
