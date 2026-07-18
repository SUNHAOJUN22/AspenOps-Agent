from __future__ import annotations

import os
import platform
import time
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import Any

import psutil

from ..compat import discover_aspen_plus_candidates
from ..convergence import ConvergenceState, classify_convergence, poll_engine_idle
from ..registry import ResolvedNode
from ..windows_job import (
    ProcessFingerprint,
    fingerprint_matches,
    is_descendant,
    process_fingerprint,
)
from .base import BackendError, SimulatorBackend

_DEFAULT_STATUS_PATHS = (
    r"\Data\Results Summary\Run-Status\Output\RUN-STATUS",
    r"\Data\Results Summary\Run-Status\Output\STATUS",
    r"\Data\Results Summary\Run-Status\Output\UOSSTAT2",
)


def _aspen_processes() -> dict[int, ProcessFingerprint]:
    result: dict[int, ProcessFingerprint] = {}
    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = str(process.info.get("name") or "").lower()
            if name not in {"aspenplus.exe", "apwn.exe"} and "aspenplus" not in name:
                continue
            pid = int(process.info["pid"])
            fingerprint = process_fingerprint(pid)
            if fingerprint is not None:
                result[pid] = fingerprint
        except (psutil.Error, KeyError, TypeError, ValueError):
            continue
    return result


def _iter_collection(collection: Any, limit: int = 200) -> Iterable[Any]:
    try:
        count = int(collection.Count)
    except Exception:
        return ()
    values: list[Any] = []
    for index in range(min(count, limit)):
        for candidate_index in (index, index + 1):
            try:
                values.append(collection.Item(candidate_index))
                break
            except Exception:
                continue
    return values


class AspenPlusBackend(SimulatorBackend):
    name = "aspen_plus"

    def __init__(self) -> None:
        self.document: Any = None
        self.progid: str | None = None
        self.model_path: Path | None = None
        self.path_cache: dict[str, str] = {}
        self.owned_processes: dict[int, ProcessFingerprint] = {}
        self.job_managed = False
        self.worker_pid = os.getpid()
        self.open_errors: list[str] = []
        self.convergence_nodes: tuple[ResolvedNode, ...] = ()
        self._coinitialized = False

    def set_process_supervision(self, job_managed: bool) -> None:
        self.job_managed = job_managed

    def open(self, model_path: Path, *, visible: bool = False) -> None:
        if platform.system() != "Windows":
            raise BackendError("Aspen Plus COM backend requires native Windows Python")
        try:
            import pythoncom
            import win32com.client
        except ImportError as exc:
            raise BackendError("Install the 'windows' extra to use Aspen Plus") from exc
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        self._coinitialized = True
        before = _aspen_processes()
        path = model_path.expanduser().resolve()
        if not path.is_file():
            raise BackendError(f"Aspen model does not exist: {path}")
        for candidate in discover_aspen_plus_candidates():
            document: Any = None
            try:
                document = win32com.client.DispatchEx(candidate.progid)  # type: ignore[no-untyped-call]
                self._set_if_available(document, "SuppressDialogs", True)
                self._open_document(document, path)
                self._set_if_available(document, "Visible", int(visible))
                self.document = document
                self.progid = candidate.progid
                self.model_path = path
                break
            except Exception as exc:
                self.open_errors.append(f"{candidate.progid}: {type(exc).__name__}: {exc}")
                if document is not None:
                    with suppress(Exception):
                        document.Close(False)
        if self.document is None:
            raise BackendError(
                "Unable to create Aspen Plus Automation Server. Tried registered ProgIDs: "
                + " | ".join(self.open_errors)
            )
        time.sleep(float(os.getenv("ASPENOPS_COM_SETTLE_S", "0.25")))
        after = _aspen_processes()
        self.owned_processes = {
            pid: fingerprint
            for pid, fingerprint in after.items()
            if pid not in before and is_descendant(pid, self.worker_pid)
        }

    def configure_convergence_nodes(self, nodes: list[ResolvedNode]) -> None:
        self.convergence_nodes = tuple(nodes)

    @staticmethod
    def _set_if_available(obj: Any, name: str, value: Any) -> None:
        with suppress(Exception):
            setattr(obj, name, value)

    @staticmethod
    def _open_document(document: Any, path: Path) -> None:
        suffix = path.suffix.lower()
        methods = (("InitFromArchive2",) if suffix in {".bkp", ".apwz"} else ()) + (
            "InitFromFile2",
            "InitFromArchive2",
            "InitFromFile",
        )
        errors: list[str] = []
        for method_name in methods:
            method = getattr(document, method_name, None)
            if not callable(method):
                continue
            try:
                method(str(path))
                return
            except Exception as exc:
                errors.append(f"{method_name}: {exc}")
        message = "No compatible Aspen document-open method succeeded: " + " | ".join(errors)
        raise BackendError(message)

    def close(self) -> None:
        if self.document is not None:
            with suppress(Exception):
                self.document.Close(False)
            self.document = None
        self.path_cache.clear()
        if self._coinitialized:
            with suppress(Exception):
                import pythoncom

                pythoncom.CoUninitialize()
            self._coinitialized = False

    def cleanup_owned_pids(self) -> None:
        if self.job_managed:
            return
        for fingerprint in sorted(self.owned_processes.values(), key=lambda item: item.pid):
            if not fingerprint_matches(fingerprint):
                continue
            if not is_descendant(fingerprint.pid, self.worker_pid):
                continue
            try:
                process = psutil.Process(fingerprint.pid)
                process.terminate()
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                if fingerprint_matches(fingerprint):
                    with suppress(psutil.Error):
                        process.kill()
            except psutil.Error:
                continue

    def reinitialize(self) -> None:
        if self.document is None:
            raise BackendError("No Aspen document is open")
        engine = getattr(self.document, "Engine", None)
        errors: list[str] = []
        for owner, method_name in ((self.document, "Reinit"), (engine, "Reinit")):
            method = getattr(owner, method_name, None)
            if callable(method):
                try:
                    method()
                    self.path_cache.clear()
                    return
                except Exception as exc:
                    errors.append(f"{method_name}: {exc}")
        raise BackendError("Aspen reinitialization failed: " + " | ".join(errors))

    def _find_node(self, node: ResolvedNode) -> Any:
        if self.document is None:
            raise BackendError("No Aspen document is open")
        cache_key = node.key + repr(sorted(node.identifiers.items()))
        cached_path = self.path_cache.get(cache_key)
        if cached_path:
            with suppress(Exception):
                candidate = self.document.Tree.FindNode(cached_path)
                if candidate is not None:
                    return candidate
            self.path_cache.pop(cache_key, None)
        errors: list[str] = []
        for path in node.paths:
            try:
                candidate = self.document.Tree.FindNode(path)
                if candidate is not None:
                    self.path_cache[cache_key] = path
                    return candidate
            except Exception as exc:
                errors.append(f"{path}: {type(exc).__name__}: {exc}")
        raise BackendError(f"No Aspen node resolved for {node.key}: {' | '.join(errors)}")

    def write(self, node: ResolvedNode, value: Any) -> None:
        target = self._find_node(node)
        target.Value = value
        observed = target.Value
        if isinstance(value, (int, float)) and isinstance(observed, (int, float)):
            tolerance = 1e-10 + 1e-8 * max(abs(float(value)), 1.0)
            if abs(float(observed) - float(value)) > tolerance:
                raise BackendError(
                    "Aspen write verification failed for "
                    f"{node.key}: requested={value}, observed={observed}"
                )

    def read(self, node: ResolvedNode) -> Any:
        return self._find_node(node).Value

    def _status_values(self) -> list[dict[str, Any]]:
        if self.document is None:
            return []
        output: list[dict[str, Any]] = []
        for node in self.convergence_nodes:
            try:
                output.append(
                    {
                        "key": node.key,
                        "source": "registry",
                        "value": self.read(node),
                    }
                )
            except Exception as exc:
                output.append(
                    {
                        "key": node.key,
                        "source": "registry",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        extra = tuple(
            item.strip()
            for item in os.getenv("ASPENOPS_STATUS_PATHS", "").split(";")
            if item.strip()
        )
        for path in (*extra, *_DEFAULT_STATUS_PATHS):
            try:
                node = self.document.Tree.FindNode(path)
                if node is not None:
                    output.append({"path": path, "source": "default", "value": node.Value})
            except Exception:
                continue
        return output

    def _engine_messages(self) -> list[str]:
        if self.document is None:
            return []
        engine = getattr(self.document, "Engine", None)
        messages: list[str] = []
        for name in ("Errors", "Messages", "Warnings"):
            collection = getattr(engine, name, None)
            if collection is None:
                continue
            for item in _iter_collection(collection):
                text = None
                for attribute in ("Description", "Text", "Message", "Value"):
                    with suppress(Exception):
                        text = getattr(item, attribute)
                    if text:
                        break
                messages.append(str(text if text is not None else item))
        return messages[:200]

    @staticmethod
    def _engine_running(engine: Any) -> bool | None:
        for attribute in ("IsRunning", "Running"):
            try:
                value = getattr(engine, attribute)
                if callable(value):
                    value = value()
                return bool(value)
            except Exception:
                continue
        return None

    def run(self) -> dict[str, Any]:
        if self.document is None:
            raise BackendError("No Aspen document is open")
        started = time.perf_counter()
        engine = self.document.Engine
        engine.Run2()
        idle = poll_engine_idle(
            lambda: self._engine_running(engine),
            timeout_s=float(os.getenv("ASPENOPS_STATUS_TIMEOUT_S", "2.0")),
            poll_interval_s=float(os.getenv("ASPENOPS_STATUS_POLL_S", "0.1")),
            stable_samples=int(os.getenv("ASPENOPS_STATUS_STABLE_SAMPLES", "2")),
        )
        status_values = self._status_values()
        messages = self._engine_messages()
        evidence = classify_convergence(
            engine_returned=True,
            idle=idle,
            status_nodes=status_values,
            messages=messages,
            source="aspen_plus",
        )
        return {
            "engine_returned": True,
            "engine_idle": evidence.engine_idle,
            "converged": evidence.state is ConvergenceState.CONVERGED,
            "convergence_state": evidence.state.value,
            "convergence_evidence": evidence.to_dict(),
            "status_nodes": status_values,
            "messages": messages,
            "positive_markers": list(evidence.positive_markers),
            "negative_markers": list(evidence.negative_markers),
            "backend": self.name,
            "progid": self.progid,
            "solve_elapsed_s": time.perf_counter() - started,
            "owned_pids": sorted(self.owned_processes),
            "job_managed": self.job_managed,
        }

    def runtime_identity(self) -> dict[str, Any]:
        exposed: dict[str, Any] = {}
        if self.document is not None:
            for attribute in ("Version", "VersionNumber", "Name", "FullName"):
                with suppress(Exception):
                    value = getattr(self.document, attribute)
                    if value is not None:
                        exposed[attribute] = str(value)
        return {
            "backend": self.name,
            "progid": self.progid,
            "exposed": exposed,
            "platform": platform.platform(),
            "model_path": None if self.model_path is None else str(self.model_path),
            "capabilities": self.capabilities(),
        }
