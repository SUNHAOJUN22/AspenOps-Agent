from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..registry import ResolvedNode


class BackendError(RuntimeError):
    pass


class TransactionState(StrEnum):
    PREPARED = "prepared"
    APPLYING = "applying"
    VERIFIED = "verified"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"
    TAINTED = "tainted"


@dataclass(slots=True)
class WriteTransactionError(BackendError):
    state: TransactionState
    cause: BaseException
    rollback_errors: tuple[str, ...] = ()

    def __str__(self) -> str:
        suffix = "" if not self.rollback_errors else f"; rollback_errors={self.rollback_errors!r}"
        return f"write transaction {self.state}: {type(self.cause).__name__}: {self.cause}{suffix}"


class SimulatorBackend(ABC):
    name: str
    rollback_abs_tol: float = 1e-10
    rollback_rel_tol: float = 1e-8
    rollback_floor: float = 1.0

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

    def capabilities(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "bulk_read": "simulated",
            "bulk_write": "simulated",
            "rollback": "verified_best_effort",
            "process_isolation_required": self.name != "mock",
        }

    def values_equal(self, observed: Any, expected: Any) -> bool:
        """Compare backend values while preserving exact semantics for discrete data."""
        if isinstance(observed, bool | str) or isinstance(expected, bool | str):
            return type(observed) is type(expected) and observed == expected
        try:
            observed_value = float(observed)
            expected_value = float(expected)
        except (TypeError, ValueError):
            return observed == expected
        if not math.isfinite(observed_value) or not math.isfinite(expected_value):
            return observed_value == expected_value
        absolute = abs(observed_value - expected_value)
        scale = max(abs(observed_value), abs(expected_value), self.rollback_floor)
        return absolute <= self.rollback_abs_tol or absolute / scale <= self.rollback_rel_tol

    def bulk_write(self, items: list[tuple[ResolvedNode, Any]]) -> None:
        """Apply writes with verified best-effort rollback.

        Every original is captured before any mutation. If a write or its backend-specific
        read-after-write verification fails, all nodes that may have been touched are restored and
        verified. A failed verification taints the worker and must trigger recycling upstream.
        """
        if not items:
            return
        originals: list[tuple[ResolvedNode, Any]] = []
        try:
            for node, _ in items:
                originals.append((node, self.read(node)))
        except Exception as exc:
            raise WriteTransactionError(TransactionState.PREPARED, exc) from exc

        touched = 0
        try:
            for node, value in items:
                touched += 1
                self.write(node, value)
        except Exception as exc:
            rollback_errors: list[str] = []
            for node, original in reversed(originals[:touched]):
                try:
                    self.write(node, original)
                    observed = self.read(node)
                    if not self.values_equal(observed, original):
                        rollback_errors.append(
                            f"{node.key}: rollback verification mismatch "
                            f"{observed!r} != {original!r}"
                        )
                except Exception as rollback_exc:
                    rollback_errors.append(
                        f"{node.key}: {type(rollback_exc).__name__}: {rollback_exc}"
                    )
            state = (
                TransactionState.TAINTED if rollback_errors else TransactionState.ROLLED_BACK
            )
            raise WriteTransactionError(state, exc, tuple(rollback_errors)) from exc

    def bulk_read(self, nodes: list[ResolvedNode]) -> list[Any]:
        return [self.read(node) for node in nodes]
