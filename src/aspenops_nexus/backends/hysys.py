from __future__ import annotations

import math
import os
import platform
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..compat import discover_hysys_candidates
from ..convergence import ConvergenceState, classify_convergence, poll_engine_idle
from ..registry import ResolvedNode
from .base import BackendError, SimulatorBackend


class HysysBackend(SimulatorBackend):
    """Conservative HYSYS adapter using a project-owned Spreadsheet contract."""

    name = "hysys"

    def __init__(self) -> None:
        self.application: Any = None
        self.case: Any = None
        self.model_path: Path | None = None
        self.progid: str | None = None
        self.open_errors: list[str] = []
        self.convergence_nodes: tuple[ResolvedNode, ...] = ()
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

    def configure_convergence_nodes(self, nodes: list[ResolvedNode]) -> None:
        self.convergence_nodes = tuple(nodes)

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

    @staticmethod
    def _solver_running(solver: Any) -> bool | None:
        for attribute in ("IsSolving", "Solving"):
            try:
                value = getattr(solver, attribute)
                if callable(value):
                    value = value()
                return bool(value)
            except Exception:
                continue
        return None

    @staticmethod
    def _contract_value_matches(observed: Any, expected: Any) -> bool:
        if isinstance(expected, bool):
            return isinstance(observed, bool) and observed is expected
        if isinstance(expected, str):
            return isinstance(observed, str) and observed.strip().casefold() == expected.strip().casefold()
        if isinstance(expected, int | float) and not isinstance(expected, bool):
            if isinstance(observed, bool) or not isinstance(observed, int | float):
                return False
            observed_number = float(observed)
            expected_number = float(expected)
            return math.isfinite(observed_number) and observed_number == expected_number
        return False

    @classmethod
    def _normalize_convergence_value(cls, value: Any, node: ResolvedNode) -> Any:
        locator = node.locator
        for expected in locator.get("converged_values", []):
            if cls._contract_value_matches(value, expected):
                return "converged"
        for expected in locator.get("not_converged_values", []):
            if cls._contract_value_matches(value, expected):
                return "not converged"

        operator = locator.get("convergence_operator")
        if operator is not None:
            if isinstance(value, bool) or not isinstance(value, int | float):
                return value
            numeric = float(value)
            if not math.isfinite(numeric):
                return value
            threshold = float(locator["convergence_threshold"])
            tolerance = float(locator.get("convergence_tolerance", 0.0))
            comparisons = {
                ">=": numeric >= threshold - tolerance,
                ">": numeric > threshold + tolerance,
                "<=": numeric <= threshold + tolerance,
                "<": numeric < threshold - tolerance,
                "==": abs(numeric - threshold) <= tolerance,
            }
            return "converged" if comparisons[str(operator)] else "not converged"

        if isinstance(value, bool):
            return "converged" if value else "not converged"
        if isinstance(value, (int, float)):
            numeric = float(value)
            if numeric == 1.0:
                return "converged"
            if numeric == 0.0:
                return "not converged"
        return value

    def _status_values(self) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for node in self.convergence_nodes:
            try:
                raw = self.read(node)
                output.append(
                    {
                        "key": node.key,
                        "source": "registry",
                        "raw_value": raw,
                        "value": self._normalize_convergence_value(raw, node),
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
        return output

    def run(self) -> dict[str, Any]:
        if self.case is None:
            raise BackendError("No HYSYS case is open")
        started = time.perf_counter()
        solver = self.case.Solver
        solver.CanSolve = True
        idle = poll_engine_idle(
            lambda: self._solver_running(solver),
            timeout_s=float(os.getenv("ASPENOPS_HYSYS_STATUS_TIMEOUT_S", "1200")),
            poll_interval_s=float(os.getenv("ASPENOPS_HYSYS_STATUS_POLL_S", "0.25")),
            stable_samples=int(os.getenv("ASPENOPS_HYSYS_STATUS_STABLE_SAMPLES", "3")),
        )
        status_values = self._status_values()
        evidence = classify_convergence(
            engine_returned=True,
            idle=idle,
            status_nodes=status_values,
            messages=[],
            source="hysys",
        )
        return {
            "engine_returned": True,
            "engine_idle": evidence.engine_idle,
            "converged": evidence.state is ConvergenceState.CONVERGED,
            "convergence_state": evidence.state.value,
            "convergence_evidence": evidence.to_dict(),
            "status_nodes": status_values,
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
            "convergence_contract_nodes": [node.key for node in self.convergence_nodes],
            "capabilities": self.capabilities(),
        }
