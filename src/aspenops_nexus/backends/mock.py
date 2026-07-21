from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from ..registry import ResolvedNode
from .base import BackendError, SimulatorBackend


class MockBackend(SimulatorBackend):
    """Deterministic nonlinear surrogate used only to validate the orchestration layer."""

    name = "mock"

    def __init__(self) -> None:
        self.model_path: Path | None = None
        self.data: dict[str, Any] = {}
        self.state: dict[str, Any] = {}
        self._initial: dict[str, Any] = {}
        self.solve_count = 0

    def open(self, model_path: Path, *, visible: bool = False) -> None:
        del visible
        self.model_path = model_path
        self.data = json.loads(model_path.read_text(encoding="utf-8"))
        self._initial = dict(self.data.get("inputs", {}))
        self.state = dict(self._initial)
        self._solve()

    def close(self) -> None:
        self.model_path = None
        self.data = {}
        self.state = {}

    def reinitialize(self) -> None:
        self.state = dict(self._initial)
        self._solve()

    @staticmethod
    def _locator(node: ResolvedNode) -> str:
        if "mock_key" in node.locator:
            return str(node.locator["mock_key"])
        if node.paths:
            return node.paths[0]
        return node.key

    def write(self, node: ResolvedNode, value: Any) -> None:
        self.state[self._locator(node)] = value

    def read(self, node: ResolvedNode) -> Any:
        key = self._locator(node)
        if key not in self.state:
            raise BackendError(f"Mock key not found: {key}")
        return self.state[key]

    def run(self) -> dict[str, Any]:
        delay_ms = float(self.data.get("solve_delay_ms", 0.0))
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        started = time.perf_counter()
        self._solve()
        self.solve_count += 1
        fail_above = self.data.get("fail_if_temperature_above")
        temperature = float(self.state.get("feed_temperature_C", 0.0))
        converged = fail_above is None or temperature <= float(fail_above)
        return {
            "engine_returned": True,
            "engine_idle": True,
            "converged": converged,
            "convergence_state": "converged" if converged else "not_converged",
            "convergence_evidence": "deterministic mock contract",
            "status": "converged" if converged else "mock convergence failure",
            "backend": self.name,
            "solve_count": self.solve_count,
            "solve_elapsed_s": time.perf_counter() - started,
        }

    def _solve(self) -> None:
        temp = float(self.state.get("feed_temperature_C", 25.0))
        pressure = float(self.state.get("feed_pressure_bar", 1.0))
        flow = float(self.state.get("feed_flow_kg_h", 100.0))
        reflux = float(self.state.get("reflux_ratio", 2.0))
        stages = float(self.state.get("stages", 20.0))
        conversion = 1.0 / (1.0 + math.exp(-(temp - 80.0) / 18.0))
        purity = max(0.0, min(0.9999, 0.78 + 0.018 * reflux + 0.003 * stages - 0.0002 * flow))
        duty = max(0.0, flow * (0.06 * temp + 1.4 * reflux + 0.08 * stages) / max(pressure, 0.1))
        self.state.update(
            {
                "conversion": conversion,
                "product_purity": purity,
                "reboiler_duty_kW": duty,
                "product_flow_kg_h": flow * conversion * purity,
            }
        )

    def runtime_identity(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "engine": "deterministic-nonlinear-mock-v2",
            "model_path": None if self.model_path is None else str(self.model_path),
            "capabilities": self.capabilities(),
        }
