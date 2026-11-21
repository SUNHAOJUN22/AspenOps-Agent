from __future__ import annotations

from typing import Any

import pytest

from aspenops_nexus.backends.aspen_plus import AspenPlusBackend
from aspenops_nexus.backends.base import BackendError, TransactionState, WriteTransactionError
from aspenops_nexus.backends.hysys import HysysBackend
from aspenops_nexus.registry import ResolvedNode


class ReadbackTarget:
    """A COM-like property that accepts a write but returns a prescribed readback."""

    def __init__(self, observed: Any) -> None:
        self.observed = observed

    @property
    def Value(self) -> Any:
        return self.observed

    @Value.setter
    def Value(self, value: Any) -> None:
        pass

    CellValue = Value


@pytest.fixture(params=[AspenPlusBackend, HysysBackend])
def backend(request: pytest.FixtureRequest) -> AspenPlusBackend | HysysBackend:
    instance: AspenPlusBackend | HysysBackend = request.param()
    return instance


def bind_target(
    backend: AspenPlusBackend | HysysBackend,
    observed: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> ResolvedNode:
    target = ReadbackTarget(observed)
    method = "_find_node" if isinstance(backend, AspenPlusBackend) else "_cell"
    monkeypatch.setattr(backend, method, lambda node: target)
    return ResolvedNode(
        key="setpoint",
        access="readwrite",
        native_unit=None,
        quantity=None,
        paths=(),
        identifiers={},
        lower=None,
        upper=None,
        integer=False,
        backend=backend.name,
        locator={},
        verification="test",
        description="setpoint readback",
    )


@pytest.mark.parametrize(
    ("requested", "observed"),
    [
        (1.0, float("nan")),
        (1.0, float("inf")),
        (1.0, float("-inf")),
        (1.0, "1.0"),
        (1.0, None),
        (1.0, True),
        (True, 1),
        ("new", "old"),
        ("1", 1),
        (1.0, 10**400),
        (1e308, -1e308),
        (1e-9, 0.0),
        (-1e-9, 0.0),
    ],
)
def test_direct_backend_write_rejects_invalid_or_changed_readback(
    backend: AspenPlusBackend | HysysBackend,
    requested: Any,
    observed: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = bind_target(backend, observed, monkeypatch)
    with pytest.raises(BackendError, match="write verification failed"):
        backend.write(node, requested)


@pytest.mark.parametrize(
    ("requested", "observed"),
    [
        (1.0, 1.0 + 1e-11),
        (1, 1.0),
        (True, True),
        ("new", "new"),
        (1e308, 1e308),
        (0.0, 0.0),
        (1e-9, 1e-9 + 1e-11),
    ],
)
def test_direct_backend_write_accepts_verified_values(
    backend: AspenPlusBackend | HysysBackend,
    requested: Any,
    observed: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = bind_target(backend, observed, monkeypatch)
    backend.write(node, requested)


def test_ignored_trace_write_is_rejected_and_its_original_is_restored(
    backend: AspenPlusBackend | HysysBackend,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = bind_target(backend, 0.0, monkeypatch)
    with pytest.raises(WriteTransactionError) as caught:
        backend.bulk_write([(node, 1e-9)])
    assert caught.value.state is TransactionState.ROLLED_BACK
    assert caught.value.rollback_errors == ()
    assert backend.read(node) == 0.0


class LostTraceRollbackTarget:
    def __init__(self) -> None:
        self.value = 1e-9

    @property
    def Value(self) -> float:
        return self.value

    @Value.setter
    def Value(self, value: float) -> None:
        if value == 1.0:
            self.value = value
            raise BackendError("transport failed after changing the setpoint")
        # Model a failed restoration that silently drops the trace original.
        self.value = 0.0

    CellValue = Value


def test_lost_trace_original_taints_a_failed_write_transaction(
    backend: AspenPlusBackend | HysysBackend,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = bind_target(backend, 1e-9, monkeypatch)
    target = LostTraceRollbackTarget()
    method = "_find_node" if isinstance(backend, AspenPlusBackend) else "_cell"
    monkeypatch.setattr(backend, method, lambda node: target)
    with pytest.raises(WriteTransactionError) as caught:
        backend.bulk_write([(node, 1.0)])
    assert caught.value.state is TransactionState.TAINTED
    assert caught.value.rollback_errors
    assert backend.read(node) == 0.0
