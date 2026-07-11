"""Deterministic nonlinear simulator used by CI and development."""

from __future__ import annotations

import json
import math
import shutil
import time
from pathlib import Path
from typing import Any

from aspenops.backends.base import RawValue, SimulatorBackend
from aspenops.errors import CaseOpenError, SimulationError
from aspenops.models import RunReport, RunState


class MockBackend(SimulatorBackend):
    name = "mock"

    def __init__(self, *, fail_on_write_path: str | None = None, run_delay_s: float = 0.0) -> None:
        self._opened = False
        self._path: Path | None = None
        self._values = self._default_values()
        self._units = self._default_units()
        self._messages: list[str] = []
        self._fail_on_write_path = fail_on_write_path
        self._run_delay_s = run_delay_s

    def open_case(self, path: Path, *, visible: bool = False, read_only: bool = False) -> None:
        del visible, read_only
        self._path = path
        if path.exists() and path.suffix.lower() == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise CaseOpenError(f"Invalid mock case: {path}") from exc
            for key, value in payload.get("values", {}).items():
                if key in self._values:
                    self._values[key] = value
        self._opened = True
        self._messages = ["Mock case opened"]

    def close(self) -> None:
        self._opened = False

    def exists(self, path: str) -> bool:
        return path in self._values

    def get_raw(self, path: str) -> RawValue:
        self._ensure_open()
        if path not in self._values:
            raise SimulationError(f"Mock path not found: {path}")
        return RawValue(self._values[path], self._units.get(path))

    def set_raw(self, path: str, value: Any, unit: str | None = None) -> None:
        self._ensure_open()
        if path not in self._values:
            raise SimulationError(f"Mock path not found: {path}")
        if self._fail_on_write_path == path:
            raise SimulationError(f"Injected write failure: {path}")
        self._values[path] = value
        if unit is not None:
            self._units[path] = unit

    def reinitialize(self) -> None:
        self._ensure_open()
        self._messages.append("Mock reinitialized")

    def run(self) -> RunReport:
        self._ensure_open()
        start = time.monotonic()
        if self._run_delay_s:
            time.sleep(self._run_delay_s)
        feed_temp = float(self._values["mock.feed.temperature"])
        feed_pressure = float(self._values["mock.feed.pressure"])
        feed_flow = float(self._values["mock.feed.mass_flow"])
        reactor_temp = float(self._values["mock.reactor.temperature"])
        residence = float(self._values["mock.reactor.residence_time"])

        if reactor_temp > 650.0 or feed_pressure > 50.0 or residence <= 0.0:
            self._messages = ["Mock solver diverged outside its stable operating envelope"]
            return RunReport(
                state=RunState.FAILED,
                elapsed_s=time.monotonic() - start,
                messages=self._messages.copy(),
                simulator_status="mock_diverged",
            )

        kinetic = 1.0 / (1.0 + math.exp(-(reactor_temp - 380.0) / 24.0))
        residence_factor = 1.0 - math.exp(-residence / 2.2)
        pressure_factor = min(1.15, max(0.75, 0.92 + 0.012 * feed_pressure))
        conversion = min(0.995, kinetic * residence_factor * pressure_factor)
        product_temp = feed_temp + 0.72 * (reactor_temp - feed_temp)
        duty = feed_flow * 3.4 * (reactor_temp - feed_temp) / 3_600.0
        yield_rate = feed_flow * conversion

        self._values.update(
            {
                "mock.product.temperature": product_temp,
                "mock.product.mass_flow": feed_flow,
                "mock.reactor.conversion": conversion,
                "mock.reactor.duty": duty,
                "mock.product.yield_rate": yield_rate,
                "mock.run.status": "converged",
            }
        )
        self._messages = ["Mock solver converged"]
        return RunReport(
            state=RunState.CONVERGED,
            elapsed_s=time.monotonic() - start,
            messages=self._messages.copy(),
            simulator_status="mock_converged",
        )

    def save(self, path: Path | None = None) -> None:
        self._ensure_open()
        target = path or self._path
        if target is None:
            raise SimulationError("Mock case has no save target")
        if target.suffix.lower() == ".json":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps({"values": self._values}, indent=2), encoding="utf-8")
        elif self._path is not None and self._path.exists() and target != self._path:
            shutil.copy2(self._path, target)

    def diagnose(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "opened": self._opened,
            "case_path": str(self._path) if self._path else None,
            "messages": self._messages.copy(),
            "node_count": len(self._values),
        }

    def _ensure_open(self) -> None:
        if not self._opened:
            raise SimulationError("No mock case is open")

    @staticmethod
    def _default_values() -> dict[str, Any]:
        return {
            "mock.feed.temperature": 80.0,
            "mock.feed.pressure": 12.0,
            "mock.feed.mass_flow": 10_000.0,
            "mock.reactor.temperature": 420.0,
            "mock.reactor.residence_time": 2.5,
            "mock.product.temperature": 0.0,
            "mock.product.mass_flow": 0.0,
            "mock.reactor.conversion": 0.0,
            "mock.reactor.duty": 0.0,
            "mock.product.yield_rate": 0.0,
            "mock.run.status": "not_run",
        }

    @staticmethod
    def _default_units() -> dict[str, str | None]:
        return {
            "mock.feed.temperature": "C",
            "mock.feed.pressure": "bar",
            "mock.feed.mass_flow": "kg/h",
            "mock.reactor.temperature": "C",
            "mock.reactor.residence_time": "h",
            "mock.product.temperature": "C",
            "mock.product.mass_flow": "kg/h",
            "mock.reactor.conversion": "fraction",
            "mock.reactor.duty": "kW",
            "mock.product.yield_rate": "kg/h",
            "mock.run.status": None,
        }
