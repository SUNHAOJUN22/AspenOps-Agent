from __future__ import annotations

import os
import platform
from contextlib import suppress
from dataclasses import asdict, dataclass
from typing import Any

import psutil


@dataclass(frozen=True, slots=True)
class ProcessFingerprint:
    pid: int
    create_time: float
    parent_pid: int
    executable: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def process_fingerprint(pid: int) -> ProcessFingerprint | None:
    try:
        process = psutil.Process(pid)
        return ProcessFingerprint(
            pid=pid,
            create_time=float(process.create_time()),
            parent_pid=int(process.ppid()),
            executable=str(process.exe()),
        )
    except (psutil.Error, OSError, ValueError):
        return None


def fingerprint_matches(expected: ProcessFingerprint) -> bool:
    observed = process_fingerprint(expected.pid)
    if observed is None:
        return False
    return (
        observed.pid == expected.pid
        and abs(observed.create_time - expected.create_time) <= 1e-6
        and observed.executable.casefold() == expected.executable.casefold()
    )


def is_descendant(pid: int, ancestor_pid: int, *, max_depth: int = 64) -> bool:
    current = pid
    visited: set[int] = set()
    for _ in range(max_depth):
        if current in visited:
            return False
        visited.add(current)
        fingerprint = process_fingerprint(current)
        if fingerprint is None:
            return False
        if fingerprint.parent_pid == ancestor_pid:
            return True
        if fingerprint.parent_pid <= 0 or fingerprint.parent_pid == current:
            return False
        current = fingerprint.parent_pid
    return False


class WindowsJobScope:
    """Best-effort Job Object supervision with KILL_ON_JOB_CLOSE.

    A process is considered job-managed only after the current Worker has been
    assigned successfully. On non-Windows hosts this object is an explicit no-op.
    """

    def __init__(self) -> None:
        self._handle: Any = None
        self._managed = False
        self._error: str | None = None

    @property
    def managed(self) -> bool:
        return self._managed

    @property
    def error(self) -> str | None:
        return self._error

    def start(self) -> bool:
        if platform.system() != "Windows":
            self._error = "Windows Job Objects are unavailable on this platform"
            return False
        try:
            import win32api
            import win32con
            import win32job

            handle = win32job.CreateJobObject(None, f"AspenOps-{os.getpid()}")
            limits = win32job.QueryInformationJobObject(
                handle,
                win32job.JobObjectExtendedLimitInformation,
            )
            limits["BasicLimitInformation"]["LimitFlags"] |= (
                win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            win32job.SetInformationJobObject(
                handle,
                win32job.JobObjectExtendedLimitInformation,
                limits,
            )
            process_handle = win32api.OpenProcess(
                win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE,
                False,
                os.getpid(),
            )
            try:
                win32job.AssignProcessToJobObject(handle, process_handle)
            finally:
                win32api.CloseHandle(process_handle)
            self._handle = handle
            self._managed = True
            return True
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            self.close()
            return False

    def identity(self) -> dict[str, Any]:
        return {
            "supported": platform.system() == "Windows",
            "managed": self._managed,
            "worker_pid": os.getpid(),
            "error": self._error,
        }

    def close(self) -> None:
        if self._handle is not None:
            with suppress(Exception):
                import win32api

                win32api.CloseHandle(self._handle)
        self._handle = None
        self._managed = False

    def __enter__(self) -> WindowsJobScope:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()
