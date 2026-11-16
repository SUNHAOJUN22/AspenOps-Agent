from __future__ import annotations

from typing import Any

import pytest

from aspenops_nexus.backends.aspen_plus import AspenPlusBackend
from aspenops_nexus.backends.base import BackendError
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
    [(1.0, 1.0 + 1e-11), (1, 1.0), (True, True), ("new", "new"), (1e308, 1e308)],
)
def test_direct_backend_write_accepts_verified_values(
    backend: AspenPlusBackend | HysysBackend,
    requested: Any,
    observed: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = bind_target(backend, observed, monkeypatch)
    backend.write(node, requested)
