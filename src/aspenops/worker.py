"""Spawned worker process that owns one simulator backend instance."""

from __future__ import annotations

import multiprocessing as mp
import threading
import traceback
from contextlib import suppress
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any

from aspenops.accessor import SemanticAccessor
from aspenops.backends import AspenPlusBackend, MockBackend, SimulatorBackend
from aspenops.errors import AccessViolation, WorkerError, WorkerTimeout
from aspenops.models import ValueRead, ValueWrite
from aspenops.registry import load_bundled_registry


def _make_backend(name: str, options: dict[str, Any]) -> SimulatorBackend:
    if name == "mock":
        return MockBackend(
            fail_on_write_path=options.get("fail_on_write_path"),
            run_delay_s=float(options.get("run_delay_s", 0.0)),
        )
    if name == "aspen_plus":
        return AspenPlusBackend()
    raise WorkerError(f"Unknown backend: {name}")


def _worker_main(connection: Connection, backend_name: str, options: dict[str, Any]) -> None:
    backend: SimulatorBackend | None = None
    state: dict[str, Any] = {"read_only": False, "opened": False}
    try:
        backend = _make_backend(backend_name, options)
        accessor = SemanticAccessor(backend, load_bundled_registry())
        connection.send({"ok": True, "result": {"backend": backend_name}})
        while True:
            request = connection.recv()
            operation = str(request["op"])
            payload = dict(request.get("payload", {}))
            if operation == "shutdown":
                connection.send({"ok": True, "result": None})
                return
            try:
                result = _dispatch(operation, payload, backend, accessor, state)
                connection.send({"ok": True, "result": result})
            except Exception as exc:
                connection.send(
                    {
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(limit=12),
                    }
                )
    except EOFError:
        return
    except Exception as exc:
        with suppress(Exception):
            connection.send(
                {
                    "ok": False,
                    "error": f"Worker startup failed: {type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(limit=12),
                }
            )
    finally:
        if backend is not None:
            with suppress(Exception):
                backend.close()
        connection.close()


def _dispatch(
    operation: str,
    payload: dict[str, Any],
    backend: SimulatorBackend,
    accessor: SemanticAccessor,
    state: dict[str, Any],
) -> Any:
    if operation == "open":
        read_only = bool(payload.get("read_only", False))
        backend.open_case(
            Path(str(payload["path"])),
            visible=bool(payload.get("visible", False)),
            read_only=read_only,
        )
        state["read_only"] = read_only
        state["opened"] = True
        accessor.clear_cache()
        return backend.diagnose()
    if operation == "close":
        backend.close()
        state["read_only"] = False
        state["opened"] = False
        accessor.clear_cache()
        return None
    if operation == "get_many":
        reads = [ValueRead.model_validate(item) for item in payload.get("reads", [])]
        return [item.model_dump(mode="json") for item in accessor.get_many(reads)]
    if operation == "set_many":
        _require_writable(state)
        writes = [ValueWrite.model_validate(item) for item in payload.get("writes", [])]
        results = accessor.set_many(writes, atomic=bool(payload.get("atomic", True)))
        return [item.model_dump(mode="json") for item in results]
    if operation == "reinitialize":
        backend.reinitialize()
        return None
    if operation == "run":
        return backend.run().model_dump(mode="json")
    if operation == "save":
        _require_writable(state)
        raw_path = payload.get("path")
        backend.save(Path(str(raw_path)) if raw_path else None)
        return None
    if operation == "diagnose":
        diagnosis = backend.diagnose()
        diagnosis["path_cache_size"] = accessor.cache_size
        diagnosis["worker_read_only"] = bool(state.get("read_only", False))
        return diagnosis
    if operation == "evaluate":
        _require_writable(state)
        writes = [ValueWrite.model_validate(item) for item in payload.get("writes", [])]
        reads = [ValueRead.model_validate(item) for item in payload.get("reads", [])]
        accessor.set_many(writes, atomic=True)
        if bool(payload.get("reinitialize", True)):
            backend.reinitialize()
        run = backend.run()
        values = accessor.get_many(reads) if run.state.value == "converged" else []
        return {
            "run": run.model_dump(mode="json"),
            "values": [item.model_dump(mode="json") for item in values],
            "diagnosis": backend.diagnose(),
        }
    raise WorkerError(f"Unsupported worker operation: {operation}")


def _require_writable(state: dict[str, Any]) -> None:
    if bool(state.get("read_only", False)):
        raise AccessViolation("Read-only worker session cannot modify or save a case")


class WorkerClient:
    """Synchronous RPC client for one persistent spawned worker.

    A dead worker is never restarted implicitly because a newly spawned process
    would not own the previously opened simulator document. Recovery therefore
    requires an explicit ``start`` followed by ``open``.
    """

    def __init__(
        self,
        backend: str,
        *,
        timeout_s: float = 120.0,
        backend_options: dict[str, Any] | None = None,
    ) -> None:
        self.backend = backend
        self.timeout_s = timeout_s
        self.backend_options = backend_options or {}
        self._process: BaseProcess | None = None
        self._connection: Connection | None = None
        self._lock = threading.RLock()

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.alive:
                return
            if self._process is not None or self._connection is not None:
                self.terminate()
            context = mp.get_context("spawn")
            parent, child = context.Pipe(duplex=True)
            process = context.Process(
                target=_worker_main,
                args=(child, self.backend, self.backend_options),
                daemon=True,
                name=f"aspenops-{self.backend}",
            )
            process.start()
            child.close()
            self._process = process
            self._connection = parent
            response = self._receive(max(5.0, self.timeout_s))
            if not response.get("ok"):
                self.terminate()
                raise WorkerError(str(response.get("error", "Worker startup failed")))

    def call(
        self,
        operation: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
    ) -> Any:
        with self._lock:
            if not self.alive:
                raise WorkerError(
                    "Worker is not running; explicitly start and reopen the case before retrying"
                )
            connection = self._require_connection()
            try:
                connection.send({"op": operation, "payload": payload or {}})
            except (BrokenPipeError, EOFError, OSError) as exc:
                self.terminate()
                raise WorkerError(f"Worker transport failed: {exc}") from exc
            response = self._receive(timeout_s or self.timeout_s)
            if not response.get("ok"):
                raise WorkerError(
                    f"{response.get('error', 'Worker request failed')}\n"
                    f"{response.get('traceback', '')}"
                )
            return response.get("result")

    def shutdown(self) -> None:
        with self._lock:
            if not self.alive:
                self.terminate()
                return
            with suppress(WorkerError):
                self.call("shutdown", timeout_s=min(10.0, self.timeout_s))
            self.terminate()

    def terminate(self) -> None:
        process = self._process
        connection = self._connection
        self._process = None
        self._connection = None
        if connection is not None:
            with suppress(OSError):
                connection.close()
        if process is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5.0)
            if process.is_alive():  # pragma: no cover - platform-dependent hard kill
                process.kill()
                process.join(timeout=2.0)

    def _receive(self, timeout_s: float) -> dict[str, Any]:
        connection = self._require_connection()
        if not connection.poll(timeout_s):
            self.terminate()
            raise WorkerTimeout(f"Worker exceeded {timeout_s:.3f} s deadline")
        try:
            response = connection.recv()
        except (EOFError, OSError) as exc:
            self.terminate()
            raise WorkerError(f"Worker exited without a response: {exc}") from exc
        if not isinstance(response, dict):
            raise WorkerError("Worker returned a non-mapping response")
        return response

    def _require_connection(self) -> Connection:
        if self._connection is None:
            raise WorkerError("Worker is not started")
        return self._connection

    def __enter__(self) -> WorkerClient:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback_obj: object) -> None:
        del exc_type, exc, traceback_obj
        self.shutdown()
