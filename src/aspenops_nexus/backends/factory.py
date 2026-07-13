from __future__ import annotations

from .aspen_plus import AspenPlusBackend
from .base import SimulatorBackend
from .hysys import HysysBackend
from .mock import MockBackend


def create_backend(name: str) -> SimulatorBackend:
    normalized = name.strip().lower()
    if normalized == "mock":
        return MockBackend()
    if normalized in {"aspen", "aspen_plus", "aspenplus"}:
        return AspenPlusBackend()
    if normalized == "hysys":
        return HysysBackend()
    raise ValueError(f"Unknown backend: {name}")
