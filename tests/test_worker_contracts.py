from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.worker as worker_module
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.worker import WorkerHandle, abort_worker, evaluate_on_worker, stop_worker

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "backend": "mock",
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "writes": [],
            "reads": [],
            "timeout_s": 0.01,
        }
    )


def result() -> EvaluationResult:
    return EvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values={"x": 1.0},
        units={"x": "1"},
        violations=[],
        diagnostics={},
        elapsed_s=0.01,
    )


class FakeProcess:
    def __init__(self, *, terminate_stops: bool = True) -> None:
        self.alive = True
        self.terminate_stops = terminate_stops
        self.terminate_calls = 0
        self.kill_calls = 0
        self.join_calls: list[float | None] = []

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.terminate_calls += 1
        if self.terminate_stops:
            self.alive = False

    def kill(self) -> None:
        self.kill_calls += 1
        self.alive = False

    def join(self, timeout: float | None = None) -> None:
        self.join_calls.append(timeout)


class FakeConnection:
    def __init__(
        self,
        *,
        poll_result: bool = True,
        response: dict[str, Any] | Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        send_error: BaseException | None = None,
        poll_error: BaseException | None = None,
        recv_error: BaseException | None = None,
    ) -> None:
        self.poll_result = poll_result
        self.response = response
        self.send_error = send_error
        self.poll_error = poll_error
        self.recv_error = recv_error
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    def send(self, obj: Any) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.sent.append(dict(obj))

    def poll(self, timeout: float = 0.0) -> bool:
        del timeout
        if self.poll_error is not None:
            raise self.poll_error
        return self.poll_result

    def recv(self) -> Any:
        if self.recv_error is not None:
            raise self.recv_error
        last = self.sent[-1]
        if callable(self.response):
            return self.response(last)
        if self.response is not None:
            return self.response
        return {"kind": "closed", "request_id": last.get("request_id")}

    def close(self) -> None:
        self.closed = True


def handle(
    tmp_path: Path,
    connection: FakeConnection,
    process: FakeProcess | None = None,
) -> WorkerHandle:
    stage = tmp_path / "stage"
    stage.mkdir(parents=True)
    staged_model = stage / "case.json"
    staged_model.write_text("{}", encoding="utf-8")
    return WorkerHandle(
        worker_id=7,
        process=process or FakeProcess(),
        connection=connection,
        staged_model=staged_model,
        runtime={"backend": "mock"},
        generation=3,
    )


def result_response(command: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol": 1,
        "kind": "result",
        "request_id": command["request_id"],
        "result": result().to_dict(),
    }


def test_evaluate_on_worker_success_correlates_and_records_runtime(tmp_path: Path) -> None:
    connection = FakeConnection(response=result_response)
    worker = handle(tmp_path, connection)

    observed = evaluate_on_worker(worker, request())

    assert observed.ok is True
    assert observed.worker_id == 7
    assert observed.diagnostics["worker"]["generation"] == 3
    assert observed.diagnostics["worker"]["runtime"] == {"backend": "mock"}
    assert observed.diagnostics["worker"]["round_trip_s"] >= 0.0
    assert worker.evaluations == 1
    assert connection.sent[0]["action"] == "evaluate"


@pytest.mark.parametrize(
    ("connection", "violation"),
    [
        (FakeConnection(send_error=BrokenPipeError("closed")), "worker_send_failed"),
        (FakeConnection(poll_error=OSError("poll")), "worker_receive_failed"),
        (FakeConnection(recv_error=EOFError("recv")), "worker_receive_failed"),
    ],
)
def test_evaluate_on_worker_converts_transport_failures(
    tmp_path: Path,
    connection: FakeConnection,
    violation: str,
) -> None:
    observed = evaluate_on_worker(handle(tmp_path, connection), request())

    assert observed.ok is False
    assert observed.violations == [violation]
    assert observed.diagnostics["generation"] == 3


def test_evaluate_on_worker_enforces_hard_timeout(tmp_path: Path) -> None:
    process = FakeProcess()
    observed = evaluate_on_worker(
        handle(tmp_path, FakeConnection(poll_result=False), process),
        request(),
    )

    assert observed.violations == ["worker_timeout"]
    assert observed.diagnostics["hard_deadline_enforced"] is True
    assert process.terminate_calls == 1
    assert process.alive is False


def test_evaluate_on_worker_rejects_protocol_mismatch(tmp_path: Path) -> None:
    connection = FakeConnection(response={"kind": "result", "request_id": "wrong"})
    observed = evaluate_on_worker(handle(tmp_path, connection), request())

    assert observed.violations == ["worker_protocol_error"]
    assert observed.diagnostics["expected_request_id"]


def test_stop_worker_closes_pipe_and_removes_staged_directory(tmp_path: Path) -> None:
    connection = FakeConnection()
    process = FakeProcess()
    worker = handle(tmp_path, connection, process)
    stage = worker.staged_model.parent

    stop_worker(worker)

    assert connection.sent[0]["action"] == "close"
    assert connection.closed is True
    assert process.terminate_calls == 1
    assert not stage.exists()


def test_stop_worker_tolerates_correlation_mismatch_and_abort_uses_kill(tmp_path: Path) -> None:
    mismatch = FakeConnection(response={"kind": "closed", "request_id": "wrong"})
    stopped = handle(tmp_path / "stopped", mismatch)
    stop_worker(stopped)
    assert mismatch.closed is True

    stubborn_process = FakeProcess(terminate_stops=False)
    aborted = handle(tmp_path / "aborted", FakeConnection(), stubborn_process)
    stage = aborted.staged_model.parent
    abort_worker(aborted)
    assert stubborn_process.terminate_calls == 1
    assert stubborn_process.kill_calls == 1
    assert not stage.exists()


class CommandConnection:
    def __init__(self, commands: list[Any]) -> None:
        self.commands = list(commands)
        self.sent: list[dict[str, Any]] = []

    def send(self, obj: Any) -> None:
        self.sent.append(dict(obj))

    def recv(self) -> Any:
        if not self.commands:
            raise EOFError
        command = self.commands.pop(0)
        if isinstance(command, BaseException):
            raise command
        return command

    def poll(self, timeout: float = 0.0) -> bool:
        del timeout
        return True

    def close(self) -> None:
        return None


class FakeScope:
    managed = True

    def __init__(self) -> None:
        self.closed = False

    def start(self) -> bool:
        return True

    def identity(self) -> dict[str, Any]:
        return {"supported": True, "managed": True, "worker_pid": 1, "error": None}

    def close(self) -> None:
        self.closed = True


class FakeBackend:
    def __init__(self, *, open_error: BaseException | None = None) -> None:
        self.open_error = open_error
        self.opened = False
        self.closed = False
        self.supervision: bool | None = None
        self.convergence_nodes: list[Any] = []
        self.cleaned = False

    def set_process_supervision(self, managed: bool) -> None:
        self.supervision = managed

    def open(self, model_path: Path, *, visible: bool = False) -> None:
        del model_path, visible
        if self.open_error is not None:
            raise self.open_error
        self.opened = True

    def configure_convergence_nodes(self, nodes: list[Any]) -> None:
        self.convergence_nodes = nodes

    def runtime_identity(self) -> dict[str, Any]:
        return {"backend": "fake"}

    def close(self) -> None:
        self.closed = True

    def cleanup_owned_pids(self) -> None:
        self.cleaned = True


def test_worker_main_handles_ping_unknown_and_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = FakeBackend()
    connection = CommandConnection(
        [
            {"action": "ping", "request_id": "p"},
            {"action": "unknown", "request_id": "u"},
            {"action": "close", "request_id": "c"},
        ]
    )
    monkeypatch.setattr(worker_module, "create_backend", lambda name: backend)
    monkeypatch.setattr(worker_module, "WindowsJobScope", FakeScope)

    worker_module._worker_main(1, 2, connection, "mock", str(MODEL), str(REGISTRY), False)

    assert [message["kind"] for message in connection.sent] == [
        "ready",
        "pong",
        "error",
        "closed",
    ]
    assert backend.opened is True
    assert backend.supervision is True
    assert backend.closed is True
    assert backend.cleaned is True


def test_worker_main_evaluates_and_serializes_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = FakeBackend()
    connection = CommandConnection(
        [
            {"action": "evaluate", "request_id": "e", "request": request().to_dict()},
            {"action": "close", "request_id": "c"},
        ]
    )
    monkeypatch.setattr(worker_module, "create_backend", lambda name: backend)
    monkeypatch.setattr(worker_module, "WindowsJobScope", FakeScope)
    monkeypatch.setattr(worker_module, "evaluate", lambda *args, **kwargs: result())

    worker_module._worker_main(1, 2, connection, "mock", str(MODEL), str(REGISTRY), False)

    result_message = connection.sent[1]
    assert result_message["kind"] == "result"
    assert result_message["request_id"] == "e"
    assert result_message["result"]["ok"] is True


def test_worker_main_reports_fatal_startup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = FakeBackend(open_error=RuntimeError("cannot open"))
    connection = CommandConnection([])
    monkeypatch.setattr(worker_module, "create_backend", lambda name: backend)
    monkeypatch.setattr(worker_module, "WindowsJobScope", FakeScope)

    worker_module._worker_main(1, 2, connection, "mock", str(MODEL), str(REGISTRY), False)

    assert connection.sent[0]["kind"] == "fatal"
    assert "cannot open" in connection.sent[0]["error"]
    assert backend.closed is True
