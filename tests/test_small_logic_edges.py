from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus import cache as cache_module
from aspenops_nexus import certification
from aspenops_nexus.backends.base import (
    SimulatorBackend,
    TransactionState,
    WriteTransactionError,
)
from aspenops_nexus.cache import ResultCache
from aspenops_nexus.config import Settings
from aspenops_nexus.design import bounded_grid, latin_hypercube, nearest_neighbor_order
from aspenops_nexus.units import UnitError, convert, dimension, supported_units


class MemoryBackend(SimulatorBackend):
    name = "mock"

    def __init__(self, values: dict[str, Any]) -> None:
        self.values = dict(values)
        self.fail_read_key: str | None = None
        self.fail_write: tuple[str, Any] | None = None
        self.opened = False
        self.reinitialized = False

    def open(self, model_path: Path, *, visible: bool = False) -> None:
        self.opened = True

    def close(self) -> None:
        self.opened = False

    def reinitialize(self) -> None:
        self.reinitialized = True

    def write(self, node: Any, value: Any) -> None:
        if self.fail_write == (node.key, value):
            raise RuntimeError("write failed")
        self.values[node.key] = value

    def read(self, node: Any) -> Any:
        if node.key == self.fail_read_key:
            raise RuntimeError("read failed")
        return self.values[node.key]

    def run(self) -> dict[str, Any]:
        return {"converged": True}

    def runtime_identity(self) -> dict[str, Any]:
        return {"backend": self.name}


def node(key: str) -> SimpleNamespace:
    return SimpleNamespace(key=key)


def test_unit_conversion_and_dimension_edges() -> None:
    units = supported_units()
    assert units["bar"] == "pressure"
    assert list(units) == sorted(units)
    assert dimension(None) is None
    assert dimension("C") == "temperature"
    with pytest.raises(UnitError, match="Unsupported unit"):
        dimension("rankine")

    assert convert(2.0, None, "bar") == 2.0
    assert convert(2.0, "bar", None) == 2.0
    assert convert(2.0, "bar", "bar") == 2.0
    assert convert(0.0, "C", "K") == pytest.approx(273.15)
    assert convert(100.0, "%", "fraction") == pytest.approx(1.0)
    with pytest.raises(UnitError, match="Unsupported unit conversion"):
        convert(1.0, "unknown", "bar")
    with pytest.raises(UnitError, match="Incompatible units"):
        convert(1.0, "bar", "kg/h")


def test_design_generators_validate_inputs_and_are_deterministic() -> None:
    with pytest.raises(ValueError, match="n must be positive"):
        latin_hypercube([(0.0, 1.0)], 0)
    with pytest.raises(ValueError, match="upper bound"):
        latin_hypercube([(1.0, 1.0)], 2)

    first = latin_hypercube([(0.0, 1.0), (10.0, 20.0)], 4, seed=7)
    second = latin_hypercube([(0.0, 1.0), (10.0, 20.0)], 4, seed=7)
    assert first == second
    assert len(first) == 4
    assert all(0.0 <= point[0] <= 1.0 for point in first)
    assert all(10.0 <= point[1] <= 20.0 for point in first)

    with pytest.raises(ValueError, match="same length"):
        bounded_grid([(0.0, 1.0)], [2, 3])
    with pytest.raises(ValueError, match="at least two"):
        bounded_grid([(0.0, 1.0)], [1])
    assert bounded_grid([(0.0, 1.0), (10.0, 20.0)], [2, 2]) == [
        [0.0, 10.0],
        [0.0, 20.0],
        [1.0, 10.0],
        [1.0, 20.0],
    ]
    assert nearest_neighbor_order([]) == []
    assert nearest_neighbor_order([[0.0], [3.0], [1.0]]) == [0, 2, 1]


def test_result_cache_empty_inputs_lru_and_hit_flush(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cache_module, "_MEMORY_MAX_ENTRIES", 2)
    monkeypatch.setattr(cache_module, "_HIT_FLUSH_THRESHOLD", 2)
    cache = ResultCache(tmp_path / "cache.sqlite3")
    assert cache.get_many([]) == {}
    cache.put_many({})
    assert cache.stats() == {"entries": 0, "hits": 0}

    cache.put_many({"a": {"value": 1}, "b": {"value": 2}})
    cache.put("a", {"value": 3})
    cache.put("c", {"value": 4})
    assert list(cache._memory) == ["a", "c"]

    assert cache.get_many(["a", "a"]) == {"a": {"value": 3}}
    assert not cache._pending_hits
    assert cache.stats() == {"entries": 3, "hits": 2}


def test_tolerance_helper_handles_discrete_nonfinite_and_numeric_values() -> None:
    assert certification._within_tolerance("a", "a", 0.0, 0.0) == (True, 0.0, 0.0)
    passed, absolute, relative = certification._within_tolerance(
        "a",
        "b",
        0.0,
        0.0,
    )
    assert passed is False
    assert math.isinf(absolute)
    assert math.isinf(relative)
    assert certification._within_tolerance(math.inf, 1.0, 1.0, 1.0)[0] is False
    assert certification._within_tolerance(1.0, 1.000001, 1e-5, 0.0)[0] is True
    assert certification._within_tolerance(100.0, 101.0, 0.0, 0.02)[0] is True


def certification_inputs(tmp_path: Path) -> tuple[dict[str, Any], Settings]:
    model = tmp_path / "model.json"
    registry = tmp_path / "registry.json"
    model.write_text("{}", encoding="utf-8")
    registry.write_text("{}", encoding="utf-8")
    data = {
        "backend": "mock",
        "model_path": str(model),
        "registry_path": str(registry),
    }
    return data, Settings(state_dir=tmp_path / "state")


def test_certification_rejects_invalid_configuration(tmp_path: Path) -> None:
    data, settings = certification_inputs(tmp_path)
    with pytest.raises(ValueError, match="at least two"):
        certification.certify_batch_document(data, settings, repeats=1)
    with pytest.raises(ValueError, match="cannot be negative"):
        certification.certify_batch_document(data, settings, abs_tol=-1.0)
    with pytest.raises(ValueError, match="cannot be negative"):
        certification.certify_batch_document(data, settings, rel_tol=-1.0)


def test_certification_reports_result_count_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data, settings = certification_inputs(tmp_path)
    responses = iter(
        [
            [{"ok": True, "values": {"x": 1.0}}],
            [
                {"ok": True, "values": {"x": 1.0}},
                {"ok": True, "values": {"x": 2.0}},
            ],
        ]
    )
    monkeypatch.setattr(
        certification,
        "run_batch_document",
        lambda request, isolated: next(responses),
    )
    report = certification.certify_batch_document(data, settings, repeats=2)
    assert report["all_runs_successful"] is True
    assert report["deterministic"] is False
    assert report["passed"] is False
    assert report["comparisons"] == [{"passed": False, "reason": "result_count_mismatch"}]


def test_certification_reports_value_ok_and_key_mismatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data, settings = certification_inputs(tmp_path)
    responses = iter(
        [
            [
                {
                    "ok": True,
                    "values": {"x": 1.0, "label": "a", "only_reference": 2.0},
                }
            ],
            [
                {
                    "ok": False,
                    "values": {"x": 1.5, "label": "b", "only_candidate": 3.0},
                }
            ],
        ]
    )
    monkeypatch.setattr(
        certification,
        "run_batch_document",
        lambda request, isolated: next(responses),
    )
    report = certification.certify_batch_document(
        data,
        settings,
        repeats=2,
        abs_tol=1e-12,
        rel_tol=1e-12,
    )
    assert report["all_runs_successful"] is False
    assert report["deterministic"] is False
    assert report["passed"] is False
    assert math.isinf(report["max_absolute_error"])
    assert {item["key"] for item in report["comparisons"]} == {
        "__ok__",
        "label",
        "only_candidate",
        "only_reference",
        "x",
    }


def test_certification_can_pass_for_identical_nonmock_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data, settings = certification_inputs(tmp_path)
    data["backend"] = "hysys"
    response = [{"ok": True, "values": {"x": 1.0, "label": "stable"}}]
    monkeypatch.setattr(
        certification,
        "run_batch_document",
        lambda request, isolated: response,
    )
    report = certification.certify_batch_document(data, settings, repeats=2)
    assert report["passed"] is True
    assert report["qualification_level"] == "licensed-simulator-runtime"
    assert report["comparisons"]


def test_backend_value_comparison_capabilities_and_noop_hooks() -> None:
    backend = MemoryBackend({"a": 1.0})
    backend.set_process_supervision(True)
    backend.configure_convergence_nodes([])
    assert backend.capabilities()["process_isolation_required"] is False
    backend.name = "aspen_plus"
    assert backend.capabilities()["process_isolation_required"] is True

    assert backend.values_equal(True, True)
    assert not backend.values_equal(True, 1)
    assert backend.values_equal(None, None)
    assert not backend.values_equal(None, 0)
    assert backend.values_equal(float("inf"), float("inf"))
    assert not backend.values_equal(float("inf"), float("-inf"))
    assert backend.values_equal(1.0, 1.0 + 1e-11)


def test_backend_bulk_write_success_prepare_failure_and_rollback() -> None:
    first = node("a")
    second = node("b")
    backend = MemoryBackend({"a": 1.0, "b": 2.0})
    backend.bulk_write([])
    backend.bulk_write([(first, 10.0)])
    assert backend.bulk_read([first, second]) == [10.0, 2.0]

    backend.fail_read_key = "b"
    with pytest.raises(WriteTransactionError) as prepared:
        backend.bulk_write([(first, 11.0), (second, 12.0)])
    assert prepared.value.state is TransactionState.PREPARED
    assert "read failed" in str(prepared.value)

    backend.fail_read_key = None
    backend.fail_write = ("b", 20.0)
    with pytest.raises(WriteTransactionError) as rolled_back:
        backend.bulk_write([(first, 10.0), (second, 20.0)])
    assert rolled_back.value.state is TransactionState.ROLLED_BACK
    assert backend.values == {"a": 10.0, "b": 2.0}

    message = str(
        WriteTransactionError(
            TransactionState.TAINTED,
            RuntimeError("boom"),
            ("a: mismatch",),
        )
    )
    assert "rollback_errors" in message
