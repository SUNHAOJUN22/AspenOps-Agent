"""Aspen Plus COM backend.

This module is import-safe on non-Windows platforms. Real execution requires
Windows, Aspen Plus, an Automation-capable installation, pywin32 and a license.
"""

from __future__ import annotations

import importlib
import platform
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from aspenops.backends.base import RawValue, SimulatorBackend
from aspenops.compat import candidate_progids
from aspenops.errors import AccessViolation, CaseOpenError, CompatibilityError, SimulationError
from aspenops.models import RunReport, RunState


class AspenPlusBackend(SimulatorBackend):
    name = "aspen_plus"

    def __init__(self) -> None:
        self._document: Any | None = None
        self._progid: str | None = None
        self._case_path: Path | None = None
        self._pythoncom: Any | None = None
        self._read_only = False

    @property
    def progid(self) -> str | None:
        return self._progid

    def open_case(self, path: Path, *, visible: bool = False, read_only: bool = False) -> None:
        if platform.system() != "Windows":
            raise CompatibilityError("Aspen Plus COM automation requires Windows")
        if not path.exists():
            raise CaseOpenError(f"Case file not found: {path}")
        self._initialize_com()
        document = self._create_document()
        with suppress(Exception):
            document.Visible = bool(visible)
        try:
            self._open_document(document, path, read_only=read_only)
        except Exception as exc:
            self._safe_quit(document)
            raise CaseOpenError(f"Could not open Aspen case {path}: {exc}") from exc
        self._document = document
        self._case_path = path
        self._read_only = read_only

    def close(self) -> None:
        document = self._document
        self._document = None
        self._case_path = None
        self._read_only = False
        if document is not None:
            self._safe_quit(document)
        if self._pythoncom is not None:
            with suppress(Exception):
                self._pythoncom.CoUninitialize()
        self._pythoncom = None

    def exists(self, path: str) -> bool:
        try:
            return self._find_node(path) is not None
        except Exception:
            return False

    def get_raw(self, path: str) -> RawValue:
        node = self._require_node(path)
        try:
            value = node.Value
        except Exception as exc:
            raise SimulationError(f"Could not read Aspen node {path}: {exc}") from exc
        unit = self._node_unit(node)
        return RawValue(value=value, unit=unit)

    def set_raw(self, path: str, value: Any, unit: str | None = None) -> None:
        if self._read_only:
            raise AccessViolation("Read-only Aspen case cannot be modified")
        node = self._require_node(path)
        try:
            setter = getattr(node, "SetValueAndUnit", None)
            if unit is not None and callable(setter):
                setter(value, unit)
            else:
                node.Value = value
        except Exception as exc:
            raise SimulationError(f"Could not write Aspen node {path}: {exc}") from exc

    def reinitialize(self) -> None:
        document = self._require_document()
        engine = getattr(document, "Engine", None)
        for target in (engine, document):
            method = getattr(target, "Reinit", None)
            if callable(method):
                method()
                return
        raise SimulationError("Aspen document does not expose Reinit")

    def run(self) -> RunReport:
        document = self._require_document()
        engine = getattr(document, "Engine", None)
        if engine is None:
            raise SimulationError("Aspen document does not expose Engine")
        start = time.monotonic()
        run_method: Callable[..., Any] | None = None
        for name in ("Run2", "Run"):
            method = getattr(engine, name, None)
            if callable(method):
                run_method = method
                break
        if run_method is None:
            raise SimulationError("Aspen Engine exposes neither Run2 nor Run")
        try:
            run_method()
            self._pump_until_idle(engine)
        except Exception as exc:
            return RunReport(
                state=RunState.FAILED,
                elapsed_s=time.monotonic() - start,
                messages=[f"Aspen run call failed: {exc}"],
                simulator_status=self._read_status(document, engine),
            )
        status = self._read_status(document, engine)
        messages = self._collect_messages(document, engine)
        state = self._classify_status(status, messages)
        if state == RunState.FAILED and not messages:
            messages = ["Aspen completed with explicit failure evidence"]
        elif state == RunState.UNKNOWN and not messages:
            messages = ["Aspen completed without explicit convergence evidence"]
        return RunReport(
            state=state,
            elapsed_s=time.monotonic() - start,
            messages=messages,
            simulator_status=status,
        )

    def save(self, path: Path | None = None) -> None:
        if self._read_only:
            raise AccessViolation("Read-only Aspen case cannot be saved")
        document = self._require_document()
        target = path
        try:
            if target is None or target == self._case_path:
                save = getattr(document, "Save", None)
                if callable(save):
                    save()
                    return
            else:
                for name in ("SaveAs", "SaveAs2"):
                    method = getattr(document, name, None)
                    if callable(method):
                        method(str(target))
                        self._case_path = target
                        return
        except Exception as exc:
            raise SimulationError(f"Could not save Aspen case: {exc}") from exc
        raise SimulationError("Aspen document does not expose a supported save method")

    def diagnose(self) -> dict[str, Any]:
        document = self._document
        engine = getattr(document, "Engine", None) if document is not None else None
        return {
            "backend": self.name,
            "opened": document is not None,
            "case_path": str(self._case_path) if self._case_path else None,
            "progid": self._progid,
            "version": self._first_property(
                document, ("Version", "ProductVersion", "ApplicationVersion")
            ),
            "status": self._read_status(document, engine) if document is not None else None,
            "messages": self._collect_messages(document, engine) if document is not None else [],
            "read_only": self._read_only,
        }

    def _initialize_com(self) -> None:
        try:
            pythoncom: Any = importlib.import_module("pythoncom")
        except ImportError as exc:
            raise CompatibilityError("Install the 'windows' extra to use Aspen Plus") from exc
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        self._pythoncom = pythoncom

    def _create_document(self) -> Any:
        try:
            win32com_client: Any = importlib.import_module("win32com.client")
        except ImportError as exc:
            raise CompatibilityError("Install the 'windows' extra to use Aspen Plus") from exc
        errors: list[str] = []
        for progid in candidate_progids():
            try:
                document = win32com_client.DispatchEx(progid)
            except Exception as exc:
                errors.append(f"{progid}: {exc}")
                continue
            self._progid = progid
            return document
        raise CompatibilityError(
            "Could not create an Aspen Automation document. Attempts: " + "; ".join(errors)
        )

    def _open_document(self, document: Any, path: Path, *, read_only: bool) -> None:
        extension = path.suffix.lower()
        if extension not in {".bkp", ".apw", ".apwz"}:
            raise CaseOpenError(f"Unsupported Aspen case extension: {extension}")
        if extension == ".bkp":
            method_names = ("InitFromArchive2", "InitFromArchive", "InitFromFile2", "InitFromFile")
        else:
            method_names = ("InitFromFile2", "InitFromFile", "InitFromArchive2", "InitFromArchive")
        errors: list[str] = []
        for name in method_names:
            method = getattr(document, name, None)
            if not callable(method):
                continue
            try:
                if read_only:
                    method(str(path), True)
                else:
                    method(str(path))
                return
            except TypeError as exc:
                if read_only:
                    errors.append(f"{name}: read-only signature unsupported ({exc})")
                else:
                    errors.append(f"{name}: {exc}")
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        mode = "read-only " if read_only else ""
        raise CaseOpenError(f"No Aspen {mode}open method succeeded: " + "; ".join(errors))

    def _find_node(self, path: str) -> Any | None:
        document = self._require_document()
        tree = getattr(document, "Tree", None)
        if tree is None:
            raise SimulationError("Aspen document does not expose Tree")
        return tree.FindNode(path)

    def _require_node(self, path: str) -> Any:
        node = self._find_node(path)
        if node is None:
            raise SimulationError(f"Aspen node not found: {path}")
        return node

    def _require_document(self) -> Any:
        if self._document is None:
            raise SimulationError("No Aspen case is open")
        return self._document

    def _pump_until_idle(self, engine: Any) -> None:
        for _ in range(3_600_000):
            running = self._first_property(engine, ("IsRunning", "Running"))
            if not bool(running):
                return
            if self._pythoncom is not None:
                self._pythoncom.PumpWaitingMessages()
            time.sleep(0.05)
        raise SimulationError("Aspen Engine remained running beyond internal safety loop")

    @staticmethod
    def _node_unit(node: Any) -> str | None:
        for name in ("UnitString", "UnitName", "Units"):
            try:
                value = getattr(node, name)
            except Exception:
                continue
            if value:
                return str(value)
        return None

    @staticmethod
    def _first_property(target: Any, names: tuple[str, ...]) -> Any | None:
        if target is None:
            return None
        for name in names:
            try:
                value = getattr(target, name)
            except Exception:
                continue
            if value is not None:
                return value
        return None

    def _read_status(self, document: Any, engine: Any) -> str | None:
        value = self._first_property(engine, ("RunStatus", "Status"))
        if value is None:
            value = self._first_property(document, ("RunStatus", "Status"))
        return None if value is None else str(value)

    @staticmethod
    def _classify_status(status: str | None, messages: list[str] | None = None) -> RunState:
        evidence = " ".join([status or "", *(messages or [])]).lower()
        failure_tokens = (
            "error",
            "fail",
            "diverg",
            "incomplete",
            "aborted",
            "fatal",
            "not converged",
        )
        if any(token in evidence for token in failure_tokens):
            return RunState.FAILED
        if status is None:
            return RunState.UNKNOWN
        lowered = status.strip().lower()
        success_tokens = (
            "converged",
            "completed",
            "complete",
            "success",
            "successful",
            "finished",
            "done",
        )
        if any(token in lowered for token in success_tokens):
            return RunState.CONVERGED
        return RunState.UNKNOWN

    def _collect_messages(self, document: Any, engine: Any) -> list[str]:
        messages: list[str] = []
        for target in (engine, document):
            for name in ("LastError", "ErrorMessage", "Message", "StatusMessage"):
                value = self._first_property(target, (name,))
                if value and str(value) not in messages:
                    messages.append(str(value))
        return messages[:20]

    @staticmethod
    def _safe_quit(document: Any) -> None:
        for name in ("Close", "Quit"):
            method = getattr(document, name, None)
            if callable(method):
                with suppress(Exception):
                    method()
