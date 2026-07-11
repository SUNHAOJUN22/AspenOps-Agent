"""Simulator backend contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aspenops.models import RunReport


@dataclass(frozen=True)
class RawValue:
    value: float | int | str | bool | None
    unit: str | None = None


class SimulatorBackend(ABC):
    name: str

    @abstractmethod
    def open_case(self, path: Path, *, visible: bool = False, read_only: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_raw(self, path: str) -> RawValue:
        raise NotImplementedError

    @abstractmethod
    def set_raw(self, path: str, value: Any, unit: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def reinitialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def run(self) -> RunReport:
        raise NotImplementedError

    @abstractmethod
    def save(self, path: Path | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def diagnose(self) -> dict[str, Any]:
        raise NotImplementedError
