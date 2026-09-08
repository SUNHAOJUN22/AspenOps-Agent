from __future__ import annotations

from dataclasses import replace

import pytest

from aspenops_nexus.windows_job import (
    ProcessFingerprint,
    WindowsJobScope,
    fingerprint_matches,
    is_descendant,
)


class FakeProcess:
    def __init__(self, pid: int, create_time: float, parent_pid: int, executable: str):
        self.pid = pid
        self._create_time = create_time
        self._parent_pid = parent_pid
        self._executable = executable

    def create_time(self) -> float:
        return self._create_time

    def ppid(self) -> int:
        return self._parent_pid

    def exe(self) -> str:
        return self._executable


def test_fingerprint_rejects_pid_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = ProcessFingerprint(42, 100.0, 7, "C:/Aspen/apwn.exe")
    observed = FakeProcess(42, 200.0, 7, "C:/Aspen/apwn.exe")
    monkeypatch.setattr("psutil.Process", lambda pid: observed)
    assert fingerprint_matches(expected) is False
    monkeypatch.setattr(
        "psutil.Process",
        lambda pid: FakeProcess(pid, 100.0, 7, "c:/aspen/APWN.EXE"),
    )
    assert fingerprint_matches(expected) is True


def test_descendant_requires_a_verified_parent_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes = {
        10: FakeProcess(10, 1.0, 1, "/worker"),
        20: FakeProcess(20, 2.0, 10, "/aspen-launcher"),
        30: FakeProcess(30, 3.0, 20, "/aspen"),
        40: FakeProcess(40, 4.0, 99, "/external-aspen"),
    }
    monkeypatch.setattr("psutil.Process", lambda pid: processes[pid])
    assert is_descendant(30, 10)
    assert not is_descendant(40, 10)


def test_non_windows_job_scope_is_an_explicit_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    scope = WindowsJobScope()
    assert scope.start() is False
    identity = scope.identity()
    assert identity["supported"] is False
    assert identity["managed"] is False
    assert identity["error"]
    scope.close()


def test_fingerprint_dataclass_is_immutable() -> None:
    fingerprint = ProcessFingerprint(1, 1.0, 0, "/bin/test")
    changed = replace(fingerprint, create_time=2.0)
    assert fingerprint.create_time == 1.0
    assert changed.create_time == 2.0
