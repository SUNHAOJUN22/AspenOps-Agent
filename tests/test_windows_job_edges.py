from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Any

import psutil
import pytest

from aspenops_nexus.windows_job import (
    ProcessFingerprint,
    WindowsJobScope,
    fingerprint_matches,
    is_descendant,
    process_fingerprint,
)


class ProcessRecord:
    def __init__(self, pid: int, parent: int) -> None:
        self.pid = pid
        self.parent = parent

    def create_time(self) -> float:
        return float(self.pid)

    def ppid(self) -> int:
        return self.parent

    def exe(self) -> str:
        return f"/process/{self.pid}"


def test_process_fingerprint_returns_none_for_missing_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(pid: int) -> Any:
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(psutil, "Process", missing)
    assert process_fingerprint(999999) is None
    assert fingerprint_matches(ProcessFingerprint(999999, 1.0, 0, "/missing")) is False


def test_descendant_rejects_cycles_missing_parents_and_depth_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = {
        1: ProcessRecord(1, 2),
        2: ProcessRecord(2, 1),
        3: ProcessRecord(3, 999),
        10: ProcessRecord(10, 9),
        9: ProcessRecord(9, 8),
        8: ProcessRecord(8, 7),
        7: ProcessRecord(7, 6),
    }

    def lookup(pid: int) -> ProcessRecord:
        if pid not in records:
            raise psutil.NoSuchProcess(pid)
        return records[pid]

    monkeypatch.setattr(psutil, "Process", lookup)
    assert is_descendant(1, 50) is False
    assert is_descendant(3, 50) is False
    assert is_descendant(10, 6, max_depth=2) is False
    assert is_descendant(10, 6, max_depth=8) is True


def fake_pywin32(monkeypatch: pytest.MonkeyPatch) -> tuple[list[Any], dict[str, Any]]:
    closed: list[Any] = []
    state: dict[str, Any] = {
        "assigned": None,
        "set_limits": None,
        "job_handle": object(),
        "process_handle": object(),
    }

    def create_job(security: Any, name: str) -> Any:
        assert security is None
        assert name == f"AspenOps-{os.getpid()}"
        return state["job_handle"]

    def query_information(handle: Any, information_class: int) -> dict[str, Any]:
        assert handle is state["job_handle"]
        assert information_class == 9
        return {"BasicLimitInformation": {"LimitFlags": 0}}

    def set_information(handle: Any, information_class: int, limits: dict[str, Any]) -> None:
        state["set_limits"] = (handle, information_class, limits)

    def assign(handle: Any, process_handle: Any) -> None:
        state["assigned"] = (handle, process_handle)

    win32job = SimpleNamespace(
        CreateJobObject=create_job,
        QueryInformationJobObject=query_information,
        SetInformationJobObject=set_information,
        AssignProcessToJobObject=assign,
        JobObjectExtendedLimitInformation=9,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE=0x2000,
    )
    win32api = SimpleNamespace(
        OpenProcess=lambda access, inherit, pid: state["process_handle"],
        CloseHandle=lambda handle: closed.append(handle),
    )
    win32con = SimpleNamespace(PROCESS_SET_QUOTA=0x100, PROCESS_TERMINATE=0x1)
    monkeypatch.setitem(sys.modules, "win32job", win32job)
    monkeypatch.setitem(sys.modules, "win32api", win32api)
    monkeypatch.setitem(sys.modules, "win32con", win32con)
    monkeypatch.setattr("platform.system", lambda: "Windows")
    return closed, state


def test_windows_job_scope_assigns_worker_and_closes_handles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed, state = fake_pywin32(monkeypatch)
    scope = WindowsJobScope()

    assert scope.start() is True
    assert scope.managed is True
    assert scope.error is None
    assert scope.identity() == {
        "supported": True,
        "managed": True,
        "worker_pid": os.getpid(),
        "error": None,
    }
    assert state["assigned"] == (state["job_handle"], state["process_handle"])
    limits = state["set_limits"][2]
    assert limits["BasicLimitInformation"]["LimitFlags"] & 0x2000
    assert state["process_handle"] in closed

    scope.close()
    assert state["job_handle"] in closed
    assert scope.managed is False


def test_windows_job_scope_failure_is_reported_and_context_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed, state = fake_pywin32(monkeypatch)
    failing_job = SimpleNamespace(
        CreateJobObject=lambda *args: (_ for _ in ()).throw(OSError("job denied")),
        QueryInformationJobObject=lambda *args: {},
        SetInformationJobObject=lambda *args: None,
        AssignProcessToJobObject=lambda *args: None,
        JobObjectExtendedLimitInformation=9,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE=0x2000,
    )
    monkeypatch.setitem(sys.modules, "win32job", failing_job)

    scope = WindowsJobScope()
    assert scope.start() is False
    assert scope.managed is False
    assert "job denied" in str(scope.error)
    assert state["job_handle"] not in closed

    with WindowsJobScope() as context_scope:
        assert context_scope.managed is False
    assert context_scope.managed is False
