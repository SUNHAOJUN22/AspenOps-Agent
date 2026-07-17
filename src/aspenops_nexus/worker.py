from __future__ import annotations

import multiprocessing as mp
import shutil
import tempfile
import time
import traceback
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

from .backends.factory import create_backend
from .evaluation import evaluate
from .models import EvaluationRequest, EvaluationResult
from .registry import NodeRegistry


@dataclass(slots=True)
class WorkerHandle:
    worker_id: int
    process: Any
    connection: Connection
    staged_model: Path
    runtime: dict[str, Any]
    generation: int = 0
    evaluations: int = 0
    started_monotonic: float = field(default_factory=time.monotonic)


def _worker_main(
    worker_id: int,
    generation: int,
    connection: Connection,
    backend_name: str,
    source_model: str,
    registry_path: str,
    visible: bool,
) -> None:
    backend = create_backend(backend_name)
    registry = NodeRegistry(registry_path)
    try:
        backend.open(Path(source_model), visible=visible)
        backend.configure_convergence_nodes(registry.convergence_nodes(backend_name))
        connection.send(
            {
                "protocol": 1,
                "kind": "ready",
                "worker_id": worker_id,
                "generation": generation,
                "runtime": backend.runtime_identity(),
            }
        )
        while True:
            command = connection.recv()
            request_id = str(command.get("request_id", ""))
            action = command.get("action")
            if action == "close":
                connection.send({"protocol": 1, "kind": "closed", "request_id": request_id})
                return
            if action == "evaluate":
                request = EvaluationRequest.from_dict(command["request"])
                result = evaluate(backend, registry, request, worker_id=worker_id)
                connection.send(
                    {
                        "protocol": 1,
                        "kind": "result",
                        "request_id": request_id,
                        "result": result.to_dict(),
                    }
                )
            elif action == "ping":
                connection.send(
                    {
                        "protocol": 1,
                        "kind": "pong",
                        "request_id": request_id,
                        "runtime": backend.runtime_identity(),
                    }
                )
            else:
                connection.send(
                    {
                        "protocol": 1,
                        "kind": "error",
                        "request_id": request_id,
                        "error": f"unknown action: {action}",
                    }
                )
    except EOFError:
        return
    except Exception as exc:
        with suppress(Exception):
            connection.send(
                {
                    "protocol": 1,
                    "kind": "fatal",
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                }
            )
    finally:
        try:
            backend.close()
            cleanup = getattr(backend, "cleanup_owned_pids", None)
            if callable(cleanup):
                cleanup()
        except Exception:
            pass


def start_worker(
    *,
    worker_id: int,
    backend_name: str,
    model_path: Path,
    registry_path: Path,
    visible: bool,
    startup_timeout_s: float = 90.0,
    generation: int = 0,
) -> WorkerHandle:
    stage_dir = Path(tempfile.mkdtemp(prefix=f"aspenops-w{worker_id}-g{generation}-"))
    staged_model = stage_dir / model_path.name
    shutil.copy2(model_path, staged_model)
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
            str(registry_path),
            visible,
        ),
        daemon=True,
        name=f"aspenops-worker-{worker_id}-g{generation}",
    )
    process.start()
    child.close()
    if not parent.poll(startup_timeout_s):
        process.terminate()
        process.join(timeout=5)
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise TimeoutError(f"Worker {worker_id} did not start within {startup_timeout_s}s")
    message = parent.recv()
    if message.get("kind") != "ready":
        process.terminate()
        process.join(timeout=5)
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise RuntimeError(f"Worker {worker_id} failed to start: {message}")
    return WorkerHandle(
        worker_id=worker_id,
        process=process,
        connection=parent,
        staged_model=staged_model,
        runtime=dict(message.get("runtime", {})),
        generation=generation,
    )


def _terminate(handle: WorkerHandle) -> None:
    if handle.process.is_alive():
        handle.process.terminate()
        handle.process.join(timeout=5)
    if handle.process.is_alive() and hasattr(handle.process, "kill"):
        handle.process.kill()
        handle.process.join(timeout=5)


def _cleanup_handle(handle: WorkerHandle) -> None:
    with suppress(OSError):
        handle.connection.close()
    shutil.rmtree(handle.staged_model.parent, ignore_errors=True)


def abort_worker(handle: WorkerHandle) -> None:
    """Immediately terminate only this AspenOps-owned worker and clean its staged model."""
    _terminate(handle)
    _cleanup_handle(handle)


def stop_worker(handle: WorkerHandle, timeout_s: float = 10.0) -> None:
    request_id = uuid.uuid4().hex
    try:
        if handle.process.is_alive():
            handle.connection.send({"action": "close", "request_id": request_id})
            if handle.connection.poll(timeout_s):
                message = handle.connection.recv()
                if message.get("request_id") != request_id:
                    raise RuntimeError("Worker close response correlation mismatch")
    except (EOFError, BrokenPipeError, OSError, RuntimeError):
        pass
    finally:
        _terminate(handle)
        _cleanup_handle(handle)


def _failure_result(
    handle: WorkerHandle, violation: str, diagnostics: dict[str, Any]
) -> EvaluationResult:
    return EvaluationResult(
        ok=False,
        communication_ok=False,
        engine_ok=False,
        converged=False,
        feasible=False,
        values={},
        units={},
        violations=[violation],
        diagnostics=diagnostics,
        elapsed_s=float(diagnostics.get("timeout_s", 0.0)),
        worker_id=handle.worker_id,
    )


def evaluate_on_worker(handle: WorkerHandle, request: EvaluationRequest) -> EvaluationResult:
    request_id = uuid.uuid4().hex
    sent_at = time.perf_counter()
    try:
        handle.connection.send(
            {"action": "evaluate", "request_id": request_id, "request": request.to_dict()}
        )
    except (BrokenPipeError, EOFError, OSError) as exc:
        return _failure_result(
            handle,
            "worker_send_failed",
            {"exception": f"{type(exc).__name__}: {exc}", "generation": handle.generation},
        )
    if not handle.connection.poll(request.timeout_s):
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
        message: dict[str, Any] = handle.connection.recv()
    except (EOFError, OSError) as exc:
        return _failure_result(
            handle,
            "worker_receive_failed",
            {"exception": f"{type(exc).__name__}: {exc}", "generation": handle.generation},
        )
    if message.get("request_id") != request_id or message.get("kind") != "result":
        return _failure_result(
            handle,
            "worker_protocol_error",
            {"message": message, "expected_request_id": request_id},
        )
    result = EvaluationResult.from_dict(message["result"])
    handle.evaluations += 1
    result.diagnostics.setdefault("worker", {})
    result.diagnostics["worker"].update(
        {
            "generation": handle.generation,
            "round_trip_s": time.perf_counter() - sent_at,
            "runtime": handle.runtime,
        }
    )
    return result
