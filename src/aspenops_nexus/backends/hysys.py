from __future__ import annotations

import platform
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..compat import discover_hysys_candidates
from ..registry import ResolvedNode
from .base import BackendError, SimulatorBackend


class HysysBackend(SimulatorBackend):
    """Conservative HYSYS adapter using a project-owned Spreadsheet contract.

    HYSYS exposes a broad and version-sensitive object model. AspenOps deliberately narrows the
    agent surface to cells in a designated Spreadsheet operation. The case author binds process
    variables and convergence indicators to those cells; the registry then supplies stable semantic
    keys. This avoids unrestricted COM traversal while preserving practical read/write coverage.
    """

    name = "hysys"

    def __init__(self) -> None:
        self.application: Any = None
        self.case: Any = None
        self.model_path: Path | None = None
        self.progid: str | None = None
        self.open_errors: list[str] = []
        self._coinitialized = False

    def open(self, model_path: Path, *, visible: bool = False) -> None:
        if platform.system() != "Windows":
            raise BackendError("HYSYS COM backend requires native Windows Python")
        try:
            import pythoncom
            import win32com.client
        except ImportError as exc:
            raise BackendError("Install the 'windows' extra to use HYSYS") from exc
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        self._coinitialized = True
        path = model_path.expanduser().resolve()
        if not path.is_file():
            raise BackendError(f"HYSYS case does not exist: {path}")
        for candidate in discover_hysys_candidates():
            application: Any = None
            try:
                application = win32com.client.DispatchEx(candidate.progid)  # type: ignore[no-untyped-call]
                case = application.SimulationCases.Open(str(path))
                with suppress(Exception):
                    application.Visible = bool(visible)
                with suppress(Exception):
                    case.Visible = bool(visible)
                self.application = application
                self.case = case
                self.model_path = path
                self.progid = candidate.progid
                return
            except Exception as exc:
                self.open_errors.append(f"{candidate.progid}: {type(exc).__name__}: {exc}")
                if application is not None:
                    with suppress(Exception):
                        application.Quit()
        raise BackendError(
            "Unable to create HYSYS Automation Server: " + " | ".join(self.open_errors)
        )

    def close(self) -> None:
        if self.case is not None:
            with suppress(Exception):
                self.case.Close(False)
        self.case = None
        if self.application is not None:
            with suppress(Exception):
                self.application.Quit()
        self.application = None
        if self._coinitialized:
            with suppress(Exception):
                import pythoncom

                pythoncom.CoUninitialize()
            self._coinitialized = False

    def reinitialize(self) -> None:
        if self.case is None:
            raise BackendError("No HYSYS case is open")
        solver = self.case.Solver
        try:
            solver.CanSolve = False
            solver.CanSolve = True
        except Exception as exc:
            raise BackendError(f"Unable to reset HYSYS solver: {exc}") from exc

    def _cell(self, node: ResolvedNode) -> Any:
        if self.case is None:
            raise BackendError("No HYSYS case is open")
        spreadsheet = node.locator.get("spreadsheet")
        cell = node.locator.get("cell")
        if not spreadsheet or not cell:
            raise BackendError(f"HYSYS node {node.key} requires spreadsheet and cell locators")
        try:
            sheet = self.case.Flowsheet.Operations.Item(str(spreadsheet))
            return sheet.Cell(str(cell))
        except Exception as exc:
            raise BackendError(
                "Unable to resolve HYSYS Spreadsheet cell "
                f"{spreadsheet}!{cell} for {node.key}: {exc}"
            ) from exc

    def write(self, node: ResolvedNode, value: Any) -> None:
        cell = self._cell(node)
        cell.CellValue = value
        observed = cell.CellValue
        if isinstance(value, (int, float)) and isinstance(observed, (int, float)):
            tolerance = 1e-10 + 1e-8 * max(abs(float(value)), 1.0)
            if abs(float(observed) - float(value)) > tolerance:
                raise BackendError(
                    f"HYSYS write verification failed for {node.key}: {value} != {observed}"
                )

    def read(self, node: ResolvedNode) -> Any:
        return self._cell(node).CellValue

    def run(self) -> dict[str, Any]:
        if self.case is None:
            raise BackendError("No HYSYS case is open")
        started = time.perf_counter()
        solver = self.case.Solver
        solver.CanSolve = True
        idle: bool | None = None
        for attribute in ("IsSolving", "Solving"):
            try:
                idle = not bool(getattr(solver, attribute))
                break
            except Exception:
                continue
        # HYSYS has no universally reliable case-level convergence Boolean exposed across releases.
        # A project should bind a convergence/status indicator into the Spreadsheet and
        # declare it as a constraint. The backend reports solver state honestly; evaluation
        # handles project checks.
        return {
            "engine_returned": True,
            "engine_idle": idle,
            "converged": idle is not False,
            "convergence_evidence": "solver-state; project spreadsheet constraint recommended",
            "backend": self.name,
            "progid": self.progid,
            "solve_elapsed_s": time.perf_counter() - started,
        }

    def runtime_identity(self) -> dict[str, Any]:
        exposed: dict[str, str] = {}
        for owner_name, owner in (("application", self.application), ("case", self.case)):
            if owner is None:
                continue
            for attribute in ("Version", "Name", "FullName"):
                with suppress(Exception):
                    value = getattr(owner, attribute)
                    if value is not None:
                        exposed[f"{owner_name}.{attribute}"] = str(value)
        return {
            "backend": self.name,
            "progid": self.progid,
            "platform": platform.platform(),
            "exposed": exposed,
            "model_path": None if self.model_path is None else str(self.model_path),
            "contract": "project-owned HYSYS Spreadsheet bridge",
            "capabilities": self.capabilities(),
        }
