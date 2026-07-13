"""Session service exposed to CLI and MCP clients."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aspenops.audit import AuditLog
from aspenops.errors import AccessViolation, ConfigurationError
from aspenops.models import RunReport, SessionInfo, ValueRead, ValueResult, ValueWrite
from aspenops.worker import WorkerClient


@dataclass
class _ManagedSession:
    client: WorkerClient
    backend: str
    path: Path
    read_only: bool


class SessionManager:
    def __init__(
        self,
        *,
        allowed_roots: list[Path] | None = None,
        audit_log: AuditLog | None = None,
        default_timeout_s: float = 120.0,
    ) -> None:
        self.allowed_roots = [root.resolve() for root in allowed_roots or []]
        self.audit_log = audit_log
        self.default_timeout_s = default_timeout_s
        self._sessions: dict[str, _ManagedSession] = {}
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
        client = WorkerClient(
            backend,
            timeout_s=timeout_s or self.default_timeout_s,
            backend_options=backend_options,
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
        record = _ManagedSession(
            client=client,
            backend=backend,
            path=resolved,
            read_only=read_only,
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

    def close_session(self, session_id: str) -> None:
        with self._lock:
            try:
                record = self._sessions.pop(session_id)
            except KeyError as exc:
                raise ConfigurationError(f"Unknown session: {session_id}") from exc
        record.client.shutdown()
        self._audit("session.close", {"session_id": session_id})

    def get_values(self, session_id: str, reads: list[ValueRead]) -> list[ValueResult]:
        client = self._client(session_id)
        payload = {"reads": [read.model_dump(mode="json") for read in reads]}
        raw = client.call("get_many", payload)
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
        self._require_writable(record)
        client = self._live_client(session_id, record)
        payload = {
            "writes": [write.model_dump(mode="json") for write in writes],
            "atomic": atomic,
        }
        raw = client.call("set_many", payload)
        results = [ValueResult.model_validate(item) for item in raw]
        self._audit(
            "values.write", {"session_id": session_id, "count": len(results), "atomic": atomic}
        )
        return results

    def run(self, session_id: str) -> RunReport:
        report = RunReport.model_validate(self._client(session_id).call("run"))
        self._audit("simulation.run", {"session_id": session_id, "state": report.state.value})
        return report

    def reinitialize(self, session_id: str) -> None:
        self._client(session_id).call("reinitialize")
        self._audit("simulation.reinitialize", {"session_id": session_id})

    def save(self, session_id: str, path: Path | None = None) -> None:
        record = self._record(session_id)
        self._require_writable(record)
        if path is not None:
            resolved = path.resolve()
            self._check_path(resolved)
        else:
            resolved = None
        self._live_client(session_id, record).call(
            "save", {"path": str(resolved) if resolved else None}
        )
        self._audit(
            "simulation.save",
            {"session_id": session_id, "path": str(resolved) if resolved else None},
        )

    def diagnose(self, session_id: str) -> dict[str, Any]:
        result = self._client(session_id).call("diagnose")
        if not isinstance(result, dict):
            raise TypeError("Diagnosis must be a mapping")
        return result

    def list_sessions(self) -> list[SessionInfo]:
        with self._lock:
            return [
                self._session_info(session_id, record)
                for session_id, record in self._sessions.items()
            ]

    def close_all(self) -> None:
        with self._lock:
            identifiers = list(self._sessions)
        for session_id in identifiers:
            self.close_session(session_id)

    def _record(self, session_id: str) -> _ManagedSession:
        with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError as exc:
                raise ConfigurationError(f"Unknown session: {session_id}") from exc

    def _client(self, session_id: str) -> WorkerClient:
        record = self._record(session_id)
        return self._live_client(session_id, record)

    @staticmethod
    def _live_client(session_id: str, record: _ManagedSession) -> WorkerClient:
        if not record.client.alive:
            raise ConfigurationError(
                f"Session {session_id} worker is not alive; close and reopen the session"
            )
        return record.client

    @staticmethod
    def _require_writable(record: _ManagedSession) -> None:
        if record.read_only:
            raise AccessViolation("Read-only session cannot modify or save a case")

    @staticmethod
    def _session_info(session_id: str, record: _ManagedSession) -> SessionInfo:
        return SessionInfo(
            session_id=session_id,
            backend=record.backend,
            case_path=str(record.path),
            alive=record.client.alive,
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
