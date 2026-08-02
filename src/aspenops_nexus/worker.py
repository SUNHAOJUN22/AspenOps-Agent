from __future__ import annotations

import multiprocessing as mp
import shutil
import tempfile
import time
import traceback
import uuid
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .backends.factory import create_backend
from .evaluation import evaluate
from .hashing import sha256_file
from .models import EvaluationRequest, EvaluationResult
from .registry import NodeRegistry
from .windows_job import WindowsJobScope

IPC_PROTOCOL = 1
_MAX_ERROR_TEXT = 2048
_MAX_TRACEBACK_TEXT = 8192


class IPCConnection(Protocol):
    def send(self, obj: Any) -> None: ...

    def recv(self) -> Any: ...

    def poll(self, timeout: float = 0.0) -> bool: ...

    def close(self) -> None: ...


@dataclass(slots=True)
class WorkerHandle:
    worker_id: int
    process: Any
    connection: IPCConnection
    staged_model: Path
    runtime: dict[str, Any]
    generation: int = 0
    evaluations: int = 0
    started_monotonic: float = field(default_factory=time.monotonic)
    staged_registry: Path | None = None
    model_sha256: str = ""
    registry_sha256: str = ""

    def execution_identity(self) -> dict[str, Any]:
        return {
            "model_sha256": self.model_sha256,
            "registry_sha256": self.registry_sha256,
            "backend": self.runtime.get("backend"),
            "runtime_identity": deepcopy(self.runtime),
            "worker_generation": self.generation,
        }


def _bounded_text(value: Any, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit]}...[truncated]"


def _message_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"type": type(value).__name__, "repr": _bounded_text(repr(value), 512)}
    return {
        "keys": sorted(str(key) for key in value)[:32],
        "protocol": value.get("protocol"),
        "kind": value.get("kind"),
        "request_id": _bounded_text(value.get("request_id", ""), 128),
    }


def _artifact_identity(
    *,
    model_path: Path,
    registry_path: Path,
    model_sha256: str,
    registry_sha256: str,
) -> dict[str, Any]:
    return {
        "model_sha256": model_sha256,
        "registry_sha256": registry_sha256,
        "staged_model_path": str(model_path),
        "staged_registry_path": str(registry_path),
    }


def _worker_main(
    worker_id: int,
    generation: int,
    connection: IPCConnection,
    backend_name: str,
    source_model: str,
    registry_path: str,
    visible: bool,
    expected_model_sha256: str | None = None,
    expected_registry_sha256: str | None = None,
) -> None:
    backend: Any = None
    job_scope: WindowsJobScope | None = None
    try:
        model = Path(source_model).expanduser().resolve()
        registry_file = Path(registry_path).expanduser().resolve()
        observed_model_sha256 = sha256_file(model)
        observed_registry_sha256 = sha256_file(registry_file)
        if expected_model_sha256 is not None and observed_model_sha256 != expected_model_sha256:
            raise RuntimeError("Worker staged model digest does not match the approved snapshot")
        if (
            expected_registry_sha256 is not None
            and observed_registry_sha256 != expected_registry_sha256
        ):
            raise RuntimeError("Worker staged registry digest does not match the approved snapshot")

        backend = create_backend(backend_name)
        registry = NodeRegistry(registry_file)
        if registry.sha256 != observed_registry_sha256:
            raise RuntimeError("Registry bytes changed while the Worker was loading them")

        job_scope = WindowsJobScope()
        job_scope.start()
        if backend_name != "mock" and not job_scope.managed:
            raise RuntimeError(
                "Real simulator workers require Windows Job Object supervision; "
                f"setup failed: {job_scope.error or 'unknown error'}"
            )
        backend.set_process_supervision(job_scope.managed)
        backend.open(model, visible=visible)
        if sha256_file(model) != observed_model_sha256:
            raise RuntimeError("Staged model changed while the simulator was opening it")
        backend.configure_convergence_nodes(registry.convergence_nodes(backend_name))
        runtime = backend.runtime_identity()
        if not isinstance(runtime, dict):
            raise TypeError("Backend runtime identity must be an object")
        runtime = dict(runtime)
        runtime["process_supervision"] = job_scope.identity()
        runtime["execution_artifacts"] = _artifact_identity(
            model_path=model,
            registry_path=registry_file,
            model_sha256=observed_model_sha256,
            registry_sha256=observed_registry_sha256,
        )
        connection.send(
            {
                "protocol": IPC_PROTOCOL,
                "kind": "ready",
                "worker_id": worker_id,
                "generation": generation,
                "runtime": runtime,
            }
        )
        while True:
            raw_command = connection.recv()
            if not isinstance(raw_command, dict):
                connection.send(
                    {
                        "protocol": IPC_PROTOCOL,
                        "kind": "error",
                        "request_id": "",
                        "error": "worker command must be an object",
                    }
                )
                continue
            command = raw_command
            request_id = str(command.get("request_id", ""))
            if command.get("protocol", IPC_PROTOCOL) != IPC_PROTOCOL:
                connection.send(
                    {
                        "protocol": IPC_PROTOCOL,
                        "kind": "error",
                        "request_id": request_id,
                        "error": "unsupported worker IPC protocol",
                    }
                )
                continue
            action = command.get("action")
            if action == "close":
                connection.send(
                    {
                        "protocol": IPC_PROTOCOL,
                        "kind": "closed",
                        "request_id": request_id,
                    }
                )
                return
            if action == "evaluate":
                request_payload = command.get("request")
                if not isinstance(request_payload, dict):
                    connection.send(
                        {
                            "protocol": IPC_PROTOCOL,
                            "kind": "error",
                            "request_id": request_id,
                            "error": "evaluation request must be an object",
                        }
                    )
                    continue
                request = EvaluationRequest.from_dict(request_payload)
                result = evaluate(backend, registry, request, worker_id=worker_id)
                result.diagnostics["execution_identity"] = {
                    "model_sha256": observed_model_sha256,
                    "registry_sha256": observed_registry_sha256,
                    "backend": backend_name,
                    "worker_generation": generation,
                }
                connection.send(
                    {
                        "protocol": IPC_PROTOCOL,
                        "kind": "result",
                        "request_id": request_id,
                        "result": result.to_dict(),
                    }
                )
            elif action == "ping":
                ping_runtime = backend.runtime_identity()
                if isinstance(ping_runtime, dict):
                    ping_runtime = dict(ping_runtime)
                    ping_runtime["execution_artifacts"] = runtime["execution_artifacts"]
                connection.send(
                    {
                        "protocol": IPC_PROTOCOL,
                        "kind": "pong",
                        "request_id": request_id,
                        "runtime": ping_runtime,
                    }
                )
            else:
                connection.send(
                    {
                        "protocol": IPC_PROTOCOL,
                        "kind": "error",
                        "request_id": request_id,
                        "error": _bounded_text(f"unknown action: {action}", _MAX_ERROR_TEXT),
                    }
                )
    except EOFError:
        return
    except Exception as exc:
        with suppress(Exception):
            connection.send(
                {
                    "protocol": IPC_PROTOCOL,
                    "kind": "fatal",
                    "worker_id": worker_id,
                    "generation": generation,
                    "error": _bounded_text(f"{type(exc).__name__}: {exc}", _MAX_ERROR_TEXT),
                    "traceback": _bounded_text(traceback.format_exc(limit=20), _MAX_TRACEBACK_TEXT),
                }
            )
    finally:
        if backend is not None:
            with suppress(Exception):
                backend.close()
            cleanup = getattr(backend, "cleanup_owned_pids", None)
            if callable(cleanup):
                with suppress(Exception):
                    cleanup()
        if job_scope is not None:
            with suppress(Exception):
                job_scope.close()
        with suppress(OSError):
            connection.close()


def _process_is_alive(process: Any) -> bool:
    try:
        return bool(process is not None and process.is_alive())
    except (AssertionError, AttributeError, ValueError):
        return False


def _terminate_process(process: Any) -> None:
    if not _process_is_alive(process):
        return
    with suppress(Exception):
        process.terminate()
    with suppress(Exception):
        process.join(timeout=5)
    if _process_is_alive(process) and hasattr(process, "kill"):
        with suppress(Exception):
            process.kill()
        with suppress(Exception):
            process.join(timeout=5)


def _cleanup_startup(
    *,
    stage_dir: Path,
    parent: Any,
    child: Any,
    process: Any,
) -> None:
    _terminate_process(process)
    for connection in (parent, child):
        if connection is not None:
            with suppress(OSError, ValueError):
                connection.close()
    shutil.rmtree(stage_dir, ignore_errors=True)


def _validate_ready_message(
    message: Any,
    *,
    worker_id: int,
    generation: int,
    expected_model_sha256: str | None = None,
    expected_registry_sha256: str | None = None,
) -> dict[str, Any]:
    if not isinstance(message, dict):
        raise RuntimeError(f"Worker {worker_id} returned a non-object ready message")
    if message.get("protocol") != IPC_PROTOCOL:
        raise RuntimeError(f"Worker {worker_id} returned an unsupported IPC protocol")
    if message.get("kind") != "ready":
        error = _bounded_text(message.get("error", _message_summary(message)), _MAX_ERROR_TEXT)
        raise RuntimeError(f"Worker {worker_id} failed to start: {error}")
    if message.get("worker_id") != worker_id or message.get("generation") != generation:
        raise RuntimeError(f"Worker {worker_id} ready identity mismatch")
    runtime = message.get("runtime")
    if not isinstance(runtime, dict):
        raise RuntimeError(f"Worker {worker_id} returned an invalid runtime identity")
    artifacts = runtime.get("execution_artifacts")
    if not isinstance(artifacts, dict):
        raise RuntimeError(f"Worker {worker_id} omitted execution artifact identity")
    if (
        expected_model_sha256 is not None
        and artifacts.get("model_sha256") != expected_model_sha256
    ):
        raise RuntimeError(f"Worker {worker_id} ready model digest mismatch")
    if (
        expected_registry_sha256 is not None
        and artifacts.get("registry_sha256") != expected_registry_sha256
    ):
        raise RuntimeError(f"Worker {worker_id} ready registry digest mismatch")
    return dict(runtime)


def start_worker(
    *,
    worker_id: int,
    backend_name: str,
    model_path: Path,
    registry_path: Path,
    visible: bool,
    startup_timeout_s: float = 90.0,
    generation: int = 0,
    expected_model_sha256: str | None = None,
    expected_registry_sha256: str | None = None,
) -> WorkerHandle:
    stage_dir = Path(tempfile.mkdtemp(prefix=f"aspenops-w{worker_id}-g{generation}-"))
    staged_model = stage_dir / f"model-{model_path.name}"
    staged_registry = stage_dir / f"registry-{registry_path.name}"
    parent: Any = None
    child: Any = None
    process: Any = None
    try:
        approved_model_sha256 = expected_model_sha256 or sha256_file(model_path)
        approved_registry_sha256 = expected_registry_sha256 or sha256_file(registry_path)
        shutil.copy2(model_path, staged_model)
        shutil.copy2(registry_path, staged_registry)
        staged_model_sha256 = sha256_file(staged_model)
        staged_registry_sha256 = sha256_file(staged_registry)
        if staged_model_sha256 != approved_model_sha256:
            raise RuntimeError("Model changed while the private Worker snapshot was being created")
        if staged_registry_sha256 != approved_registry_sha256:
            raise RuntimeError("Registry changed while the private Worker snapshot was being created")

        context = mp.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        process = context.Process(
            target=_worker_main,
            args=(
                worker_id,
                generation,
                child,
                backend_name,
                str(staged_model),
                str(staged_registry),
                visible,
                approved_model_sha256,
                approved_registry_sha256,
            ),
            daemon=True,
            name=f"aspenops-worker-{worker_id}-g{generation}",
        )
        process.start()
        child.close()
        child = None
        if not parent.poll(startup_timeout_s):
            raise TimeoutError(f"Worker {worker_id} did not start within {startup_timeout_s}s")
        message = parent.recv()
        runtime = _validate_ready_message(
            message,
            worker_id=worker_id,
            generation=generation,
            expected_model_sha256=approved_model_sha256,
            expected_registry_sha256=approved_registry_sha256,
        )
    except BaseException:
        _cleanup_startup(
            stage_dir=stage_dir,
            parent=parent,
            child=child,
            process=process,
        )
        raise
    return WorkerHandle(
        worker_id=worker_id,
        process=process,
        connection=parent,
        staged_model=staged_model,
        runtime=runtime,
        generation=generation,
        staged_registry=staged_registry,
        model_sha256=approved_model_sha256,
        registry_sha256=approved_registry_sha256,
    )


def _terminate(handle: WorkerHandle) -> None:
    _terminate_process(handle.process)


def _cleanup_handle(handle: WorkerHandle) -> None:
    with suppress(OSError, ValueError):
        handle.connection.close()
    shutil.rmtree(handle.staged_model.parent, ignore_errors=True)


def abort_worker(handle: WorkerHandle) -> None:
    """Immediately recycle this AspenOps-owned worker and its private artifacts."""
    _terminate(handle)
    _cleanup_handle(handle)


def _valid_close_response(message: Any, request_id: str) -> bool:
    return bool(
        isinstance(message, dict)
        and message.get("protocol") == IPC_PROTOCOL
        and message.get("kind") == "closed"
        and message.get("request_id") == request_id
    )


def stop_worker(handle: WorkerHandle, timeout_s: float = 10.0) -> None:
    request_id = uuid.uuid4().hex
    graceful = False
    try:
        if _process_is_alive(handle.process):
            handle.connection.send(
                {
                    "protocol": IPC_PROTOCOL,
                    "action": "close",
                    "request_id": request_id,
                }
            )
            if handle.connection.poll(timeout_s):
                graceful = _valid_close_response(handle.connection.recv(), request_id)
    except (EOFError, BrokenPipeError, OSError, RuntimeError, ValueError):
        graceful = False
    if graceful:
        with suppress(Exception):
            handle.process.join(timeout=timeout_s)
    if _process_is_alive(handle.process):
        _terminate(handle)
    _cleanup_handle(handle)


def _failure_result(
    handle: WorkerHandle,
    violation: str,
    diagnostics: dict[str, Any],
) -> EvaluationResult:
    normalized_diagnostics = dict(diagnostics)
    if handle.model_sha256 and handle.registry_sha256:
        normalized_diagnostics.setdefault(
            "execution_identity",
            {
                "model_sha256": handle.model_sha256,
                "registry_sha256": handle.registry_sha256,
                "backend": handle.runtime.get("backend"),
                "worker_generation": handle.generation,
            },
        )
    return EvaluationResult(
        ok=False,
        communication_ok=False,
        engine_ok=False,
        converged=False,
        feasible=False,
        values={},
        units={},
        violations=[violation],
        diagnostics=normalized_diagnostics,
        elapsed_s=float(normalized_diagnostics.get("timeout_s", 0.0)),
        worker_id=handle.worker_id,
    )


def _protocol_failure(
    handle: WorkerHandle,
    message: Any,
    request_id: str,
    detail: str,
) -> EvaluationResult:
    return _failure_result(
        handle,
        "worker_protocol_error",
        {
            "detail": detail,
            "message": _message_summary(message),
            "expected_request_id": request_id,
            "generation": handle.generation,
        },
    )


def evaluate_on_worker(handle: WorkerHandle, request: EvaluationRequest) -> EvaluationResult:
    request_id = uuid.uuid4().hex
    sent_at = time.perf_counter()
    try:
        handle.connection.send(
            {
                "protocol": IPC_PROTOCOL,
                "action": "evaluate",
                "request_id": request_id,
                "request": request.to_dict(),
            }
        )
    except (BrokenPipeError, EOFError, OSError) as exc:
        return _failure_result(
            handle,
            "worker_send_failed",
            {"exception": f"{type(exc).__name__}: {exc}", "generation": handle.generation},
        )
    try:
        response_ready = handle.connection.poll(request.timeout_s)
    except (EOFError, OSError) as exc:
        return _failure_result(
            handle,
            "worker_receive_failed",
            {"exception": f"{type(exc).__name__}: {exc}", "generation": handle.generation},
        )
    if not response_ready:
        _terminate(handle)
        return _failure_result(
            handle,
            "worker_timeout",
            {
                "timeout_s": request.timeout_s,
                "generation": handle.generation,
                "hard_deadline_enforced": True,
            },
        )
    try:
        message = handle.connection.recv()
    except (EOFError, OSError) as exc:
        return _failure_result(
            handle,
            "worker_receive_failed",
            {"exception": f"{type(exc).__name__}: {exc}", "generation": handle.generation},
        )
    if not isinstance(message, dict):
        return _protocol_failure(handle, message, request_id, "response must be an object")
    if message.get("protocol") != IPC_PROTOCOL:
        return _protocol_failure(handle, message, request_id, "protocol mismatch")
    if message.get("request_id") != request_id:
        return _protocol_failure(handle, message, request_id, "request correlation mismatch")
    if message.get("kind") != "result":
        return _protocol_failure(handle, message, request_id, "response kind must be result")
    result_payload = message.get("result")
    if not isinstance(result_payload, dict):
        return _protocol_failure(handle, message, request_id, "result payload must be an object")
    try:
        result = EvaluationResult.from_dict(result_payload)
    except (KeyError, TypeError, ValueError) as exc:
        return _protocol_failure(
            handle,
            message,
            request_id,
            f"invalid result payload: {type(exc).__name__}: {exc}",
        )
    result.worker_id = handle.worker_id
    handle.evaluations += 1
    result.diagnostics["execution_identity"] = {
        "model_sha256": handle.model_sha256,
        "registry_sha256": handle.registry_sha256,
        "backend": handle.runtime.get("backend"),
        "worker_generation": handle.generation,
    }
    worker_diagnostics = result.diagnostics.get("worker")
    if not isinstance(worker_diagnostics, dict):
        worker_diagnostics = {}
        result.diagnostics["worker"] = worker_diagnostics
    worker_diagnostics.update(
        {
            "generation": handle.generation,
            "round_trip_s": time.perf_counter() - sent_at,
            "runtime": deepcopy(handle.runtime),
        }
    )
    return result
