from pathlib import Path

import pytest

from aspenops.accessor import SemanticAccessor
from aspenops.backends.mock import MockBackend
from aspenops.errors import AccessViolation, SimulationError, UnitError, ValidationError
from aspenops.models import ValueRead, ValueWrite
from aspenops.registry import load_bundled_registry


def _opened_backend(**kwargs: object) -> MockBackend:
    backend = MockBackend(**kwargs)
    backend.open_case(Path("unused.json"))
    return backend


def test_get_many_converts_units_and_uses_cache() -> None:
    backend = _opened_backend()
    accessor = SemanticAccessor(backend, load_bundled_registry())
    results = accessor.get_many(
        [
            ValueRead(
                key="stream.input.temperature",
                identifiers={"stream": "FEED"},
                unit="K",
            )
        ]
    )
    assert results[0].value == pytest.approx(353.15)
    assert accessor.cache_size == 1
    accessor.get_many([ValueRead(key="stream.input.temperature", identifiers={"stream": "FEED"})])
    assert accessor.cache_size == 1


def test_write_validation_and_access_policy() -> None:
    accessor = SemanticAccessor(_opened_backend(), load_bundled_registry())
    with pytest.raises(ValidationError):
        accessor.set_many(
            [
                ValueWrite(
                    key="stream.input.temperature",
                    identifiers={"stream": "FEED"},
                    value=-500,
                    unit="C",
                )
            ]
        )
    with pytest.raises(UnitError):
        accessor.set_many(
            [
                ValueWrite(
                    key="stream.input.temperature",
                    identifiers={"stream": "FEED"},
                    value=1,
                    unit="bar",
                )
            ]
        )
    with pytest.raises(AccessViolation):
        accessor.set_many(
            [
                ValueWrite(
                    key="stream.output.temperature",
                    identifiers={"stream": "PRODUCT"},
                    value=100,
                    unit="C",
                )
            ]
        )


def test_atomic_batch_write_rolls_back() -> None:
    backend = _opened_backend(fail_on_write_path="mock.reactor.temperature")
    accessor = SemanticAccessor(backend, load_bundled_registry())
    original = backend.get_raw("mock.feed.temperature").value
    with pytest.raises(SimulationError):
        accessor.set_many(
            [
                ValueWrite(
                    key="stream.input.temperature",
                    identifiers={"stream": "FEED"},
                    value=120,
                    unit="C",
                ),
                ValueWrite(
                    key="block.input.temperature",
                    identifiers={"block": "R-101"},
                    value=450,
                    unit="C",
                ),
            ],
            atomic=True,
        )
    assert backend.get_raw("mock.feed.temperature").value == original
