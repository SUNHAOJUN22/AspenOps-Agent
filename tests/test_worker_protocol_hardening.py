from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.worker as worker_module
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.worker import (
    IPC_PROTOCOL,
    WorkerHandle,
    evaluate_on_worker,
    start_worker,
    stop_worker,
)

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


class FakeProcess:
    def __init__(
        self,
        *,
        start_error: BaseException | None = None,
        exit_on_join: bool = False,
    ) -> None:
        self.alive = False
        self.start_error = start_error
        self.exit_on_join = exit_on_join
        self.terminate_calls = 0
        self.kill_calls = 0
        self.join_calls: list[float | None] = []

    def start(self) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.terminate_calls += 1
        self.alive = False

    def kill(self) -> None:
        self.kill_calls += 1
        self.alive = False

    def join(self, timeout: float | None = None) -> None:
        self.join_calls.append(timeout)
        if self.exit_on_join:
            self.alive = False


class FakeConnection:
    def __init__(
        self,
        response: Any,
        *,
        poll_error: BaseException | None = None,
    ) -> None:
        self.response = response
        self.poll_error = poll_error
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    def send(self, obj: Any) -> None:
        self.sent.append(dict(obj))

    def poll(self, timeout: float = 0.0) -> bool:
        del timeout
        if self.poll_error is not None:
            raise self.poll_error
        return True

    def recv(self) -> Any:
        if callable(self.response):
            return self.response(self.sent[-1])
        return self.response

    def close(self) -> None:
        self.closed = True


def handle(tmp_path: Path, response: Any, process: FakeProcess | None = None) -> WorkerHandle:
    stage = tmp_path / "stage"
    stage.mkdir(parents=True)
    model = stage / "model.json"
    model.write_text("{}", encoding="utf-8")
    return WorkerHandle(
        worker_id=2,
        process=process or FakeProcess(),
        connection=FakeConnection(response),
        staged_model=model,
        runtime={"backend": "mock"},
        generation=4,
    )


@pytest.mark.parametrize(
    ("response", "detail"),
    [
        ("not-an-object", "response must be an object"),
        ({"protocol": 2, "kind": "result"}, "protocol mismatch"),
        ({"protocol": 1, "kind": "error"}, "request correlation mismatch"),
        (
            lambda command: {
                "protocol": 1,
                "kind": "error",
                "request_id": command["request_id"],
            },
            "response kind must be result",
        ),
        (
            lambda command: {
                "protocol": 1,
                "kind": "result",
                "request_id": command["request_id"],
                "result": [],
            },
            "result payload must be an object",
        ),
        (
            lambda command: {
                "protocol": 1,
                "kind": "result",
                "request_id": command["request_id"],
                "result": {"ok": True},
            },
            "invalid result payload",
        ),
    ],
)
def test_evaluate_rejects_malformed_protocol_payloads(
    tmp_path: Path,
    response: Any,
    detail: str,
) -> None:
    observed = evaluate_on_worker(handle(tmp_path, response), request())
    assert observed.ok is False
    assert observed.violations == ["worker_protocol_error"]
    assert detail in observed.diagnostics["detail"]
    assert observed.worker_id == 2


def test_stop_worker_allows_valid_closed_response_to_exit_without_terminate(
    tmp_path: Path,
) -> None:
    process = FakeProcess(exit_on_join=True)
    process.alive = True

    def closed(command: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocol": IPC_PROTOCOL,
            "kind": "closed",
            "request_id": command["request_id"],
        }

    worker = handle(tmp_path, closed, process)
    stage = worker.staged_model.parent
    stop_worker(worker, timeout_s=0.1)

    assert process.terminate_calls == 0
    assert process.join_calls == [0.1]
    assert worker.connection.closed is True
    assert not stage.exists()


class FakeContext:
    def __init__(self, parent: FakeConnection, child: FakeConnection, process: FakeProcess) -> None:
        self.parent = parent
        self.child = child
        self.process = process

    def Pipe(self, duplex: bool = True) -> tuple[FakeConnection, FakeConnection]:
        assert duplex is True
        return self.parent, self.child

    def Process(self, **kwargs: Any) -> FakeProcess:
        assert kwargs["target"] is worker_module._worker_main
        return self.process


def test_start_worker_rejects_invalid_ready_identity_and_cleans_every_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage = tmp_path / "stage"
    parent = FakeConnection(
        {
            "protocol": IPC_PROTOCOL,
            "kind": "ready",
            "worker_id": 99,
            "generation": 3,
            "runtime": {},
        }
    )
    child = FakeConnection(None)
    process = FakeProcess()
    context = FakeContext(parent, child, process)
    monkeypatch.setattr(worker_module.tempfile, "mkdtemp", lambda **kwargs: str(stage))
    monkeypatch.setattr(worker_module.mp, "get_context", lambda method: context)

    with pytest.raises(RuntimeError, match="identity mismatch"):
        start_worker(
            worker_id=1,
            backend_name="mock",
            model_path=MODEL,
            registry_path=REGISTRY,
            visible=False,
            generation=3,
        )

    assert parent.closed is True
    assert child.closed is True
    assert process.terminate_calls == 1
    assert not stage.exists()


def test_start_worker_cleans_stage_when_model_copy_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage = tmp_path / "copy-failure"
    monkeypatch.setattr(worker_module.tempfile, "mkdtemp", lambda **kwargs: str(stage))
    monkeypatch.setattr(
        worker_module.shutil,
        "copy2",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("copy failed")),
    )

    with pytest.raises(OSError, match="copy failed"):
        start_worker(
            worker_id=1,
            backend_name="mock",
            model_path=MODEL,
            registry_path=REGISTRY,
            visible=False,
        )
    assert not stage.exists()


def test_worker_fatal_diagnostics_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    huge = "x" * 50_000

    class Backend:
        def set_process_supervision(self, managed: bool) -> None:
            del managed

        def open(self, model_path: Path, *, visible: bool = False) -> None:
            del model_path, visible
            raise RuntimeError(huge)

        def close(self) -> None:
            return None

    class Scope:
        managed = False

        def start(self) -> bool:
            return False

        def identity(self) -> dict[str, Any]:
            return {"managed": False}

        def close(self) -> None:
            return None

    connection = FakeConnection(None)
    monkeypatch.setattr(worker_module, "create_backend", lambda name: Backend())
    monkeypatch.setattr(worker_module, "WindowsJobScope", Scope)
    worker_module._worker_main(1, 2, connection, "mock", str(MODEL), str(REGISTRY), False)

    fatal = connection.sent[0]
    assert fatal["kind"] == "fatal"
    assert fatal["protocol"] == IPC_PROTOCOL
    assert len(fatal["error"]) <= 2100
    assert len(fatal["traceback"]) <= 8300
