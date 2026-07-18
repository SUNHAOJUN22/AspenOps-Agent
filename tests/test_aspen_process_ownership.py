from __future__ import annotations

from pathlib import Path

import pytest

from aspenops_nexus.backends.aspen_plus import AspenPlusBackend
from aspenops_nexus.windows_job import ProcessFingerprint


class FakeProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float) -> None:
        del timeout

    def kill(self) -> None:
        self.killed = True


def test_cleanup_skips_unverified_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AspenPlusBackend()
    backend.worker_pid = 100
    backend.owned_processes = {
        200: ProcessFingerprint(200, 1.0, 100, "C:/Aspen/apwn.exe"),
        300: ProcessFingerprint(300, 1.0, 999, "C:/Aspen/apwn.exe"),
    }
    processes = {200: FakeProcess(200), 300: FakeProcess(300)}
    monkeypatch.setattr(
        "aspenops_nexus.backends.aspen_plus.fingerprint_matches",
        lambda fingerprint: fingerprint.pid == 200,
    )
    monkeypatch.setattr(
        "aspenops_nexus.backends.aspen_plus.is_descendant",
        lambda pid, ancestor: pid == 200 and ancestor == 100,
    )
    monkeypatch.setattr(
        "aspenops_nexus.backends.aspen_plus.psutil.Process",
        lambda pid: processes[pid],
    )
    backend.cleanup_owned_pids()
    assert processes[200].terminated is True
    assert processes[300].terminated is False


def test_job_managed_backend_never_uses_pid_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = AspenPlusBackend()
    backend.set_process_supervision(True)
    backend.owned_processes = {200: ProcessFingerprint(200, 1.0, 100, "C:/Aspen/apwn.exe")}
    monkeypatch.setattr(
        "aspenops_nexus.backends.aspen_plus.psutil.Process",
        lambda pid: pytest.fail(f"manual cleanup attempted for {pid}"),
    )
    backend.cleanup_owned_pids()


def test_backend_runtime_retains_model_path_type() -> None:
    backend = AspenPlusBackend()
    backend.model_path = Path("case.bkp")
    assert backend.runtime_identity()["model_path"].endswith("case.bkp")
