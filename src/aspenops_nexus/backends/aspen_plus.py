from __future__ import annotations

import math
import os
import platform
import time
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import Any

import psutil

from ..compat import discover_aspen_plus_candidates
from ..registry import ResolvedNode
from ..solver_status import assess_convergence
from .base import BackendError, SimulatorBackend

_DEFAULT_STATUS_PATHS = (
    r"\Data\Results Summary\Run-Status\Output\RUN-STATUS",
    r"\Data\Results Summary\Run-Status\Output\STATUS",
    r"\Data\Results Summary\Run-Status\Output\UOSSTAT2",
)


def _configured_delay(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        value = float(default if raw is None else raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite and nonnegative") from exc
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return value


def _aspen_pids() -> set[int]:
    result: set[int] = set()
    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = str(process.info.get("name") or "").lower()
            if name in {"aspenplus.exe", "apwn.exe"} or "aspenplus" in name:
                result.add(int(process.info["pid"]))
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
        self.owned_pids: set[int] = set()
        self.open_errors: list[str] = []
        self._coinitialized = False

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
        before = _aspen_pids()
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
        settle_s = _configured_delay("ASPENOPS_COM_SETTLE_S", 0.25)
        if settle_s:
            time.sleep(settle_s)
        self.owned_pids = _aspen_pids() - before

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
        for pid in sorted(self.owned_pids):
            try:
                process = psutil.Process(pid)
                process.terminate()
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
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
        extra = tuple(
            item.strip()
            for item in os.getenv("ASPENOPS_STATUS_PATHS", "").split(";")
            if item.strip()
        )
        output: list[dict[str, Any]] = []
        for path in (*extra, *_DEFAULT_STATUS_PATHS):
            try:
                node = self.document.Tree.FindNode(path)
                if node is not None:
                    output.append({"path": path, "value": node.Value})
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

    def run(self) -> dict[str, Any]:
        if self.document is None:
            raise BackendError("No Aspen document is open")
        started = time.perf_counter()
        engine = self.document.Engine
        engine.Run2()
        status_values = self._status_values()
        messages = self._engine_messages()
        engine_idle: bool | None = None
        for attribute in ("IsRunning", "Running"):
            try:
                engine_idle = not bool(getattr(engine, attribute))
                break
            except Exception:
                continue
        raw_evidence = [item.get("value") for item in status_values]
        raw_evidence.extend(messages)
        assessment = assess_convergence(raw_evidence, engine_idle)
        return {
            "engine_returned": True,
            "engine_idle": engine_idle,
            "converged": assessment.converged,
            "convergence_evidence": assessment.to_dict(),
            "status_nodes": status_values,
            "messages": messages,
            "positive_markers": list(assessment.positive_evidence),
            "negative_markers": list(assessment.negative_evidence),
            "backend": self.name,
            "progid": self.progid,
            "solve_elapsed_s": time.perf_counter() - started,
            "owned_pids": sorted(self.owned_pids),
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
