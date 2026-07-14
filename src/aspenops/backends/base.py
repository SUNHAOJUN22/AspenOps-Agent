from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..registry import ResolvedNode


class BackendError(RuntimeError):
    pass


class SimulatorBackend(ABC):
    name: str

    @abstractmethod
    def open(self, model_path: Path, *, visible: bool = False) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def reinitialize(self) -> None: ...

    @abstractmethod
    def write(self, node: ResolvedNode, value: Any) -> None: ...

    @abstractmethod
    def read(self, node: ResolvedNode) -> Any: ...

    @abstractmethod
    def run(self) -> dict[str, Any]: ...

    @abstractmethod
    def runtime_identity(self) -> dict[str, Any]: ...

    def apply_solver_options(self, options: dict[str, Any]) -> None:
        if options:
            raise BackendError(f"Backend {self.name} does not support solver_options")

    def capabilities(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "bulk_read": True,
            "bulk_write": True,
            "transactional_write": True,
            "process_isolation_required": self.name != "mock",
            "explicit_convergence_required": self.name == "hysys",
        }

    def bulk_write(self, items: list[tuple[ResolvedNode, Any]]) -> None:
        originals: list[tuple[ResolvedNode, Any]] = []
        completed = 0
        try:
            for node, value in items:
                originals.append((node, self.read(node)))
                self.write(node, value)
                completed += 1
        except Exception:
            for node, original in reversed(originals[:completed]):
                with suppress(Exception):
                    self.write(node, original)
            raise

    def bulk_read(self, nodes: list[ResolvedNode]) -> list[Any]:
        return [self.read(node) for node in nodes]
