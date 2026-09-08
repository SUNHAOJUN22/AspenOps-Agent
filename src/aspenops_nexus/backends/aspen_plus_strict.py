from __future__ import annotations

from typing import Any

from ..convergence import normalize_running_flag
from .aspen_plus import AspenPlusBackend as BaseAspenPlusBackend


class AspenPlusBackend(BaseAspenPlusBackend):
    """Aspen Plus adapter with explicit COM running-flag normalization."""

    @staticmethod
    def _engine_running(engine: Any) -> bool | None:
        for attribute in ("IsRunning", "Running"):
            try:
                value = getattr(engine, attribute)
                if callable(value):
                    value = value()
                normalized = normalize_running_flag(value)
                if normalized is not None:
                    return normalized
            except Exception:
                continue
        return None
