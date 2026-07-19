from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus import compat
from aspenops_nexus.backends.base import (
    SimulatorBackend,
    TransactionState,
    WriteTransactionError,
)
from aspenops_nexus.evaluation import (
    _constraint_violation,
    _converted,
    _finite,
    evaluate,
)
from aspenops_nexus.evaluation_plan import (
    CompiledBalance,
    CompiledBalanceTerm,
    CompiledConstraint,
    EvaluationPlan,
    IOEstimate,
    OutputBinding,
)
from aspenops_nexus.models import (
    BalanceSpec,
    BalanceTerm,
    ConstraintSpec,
    EvaluationRequest,
    VariableRead,
)
from aspenops_nexus.registry import ResolvedNode


def resolved_node(
    key: str,
    *,
    unit: str | None = None,
    identifiers: dict[str, str] | None = None,
) -> ResolvedNode:
    return ResolvedNode(
        key=key,
        access="read",
        native_unit=unit,
        quantity=None,
        paths=(key,),
        identifiers=identifiers or {},
        lower=None,
        upper=None,
        integer=False,
        backend="mock",
        locator={},
        verification="test",
        description="test node",
    )


class FakeRegistryRoot:
    def __enter__(self) -> FakeRegistryRoot:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        return None


class FakeWinreg:
    HKEY_CLASSES_ROOT = object()
    KEY_READ = 1
    KEY_WOW64_64KEY = 2
    KEY_WOW64_32KEY = 4

    def __init__(self) -> None:
        self.names = [
            "Apwn.Document.39",
            "Apwn.Document.40.0",
            "HYSYS.Application.15",
            "Unrelated.Component",
        ]

    def OpenKey(self, hive: Any, path: str, reserved: int, flags: int) -> FakeRegistryRoot:
        assert hive is self.HKEY_CLASSES_ROOT
        assert path == ""
        assert reserved == 0
        if flags & self.KEY_WOW64_32KEY:
            raise OSError("32-bit view unavailable")
        return FakeRegistryRoot()

    def QueryInfoKey(self, root: FakeRegistryRoot) -> tuple[int, int, int]:
        return (len(self.names), 0, 0)

    def EnumKey(self, root: FakeRegistryRoot, index: int) -> str:
        return self.names[index]


def test_registry_enumeration_filters_prefixes_and_skips_failed_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeWinreg()
    monkeypatch.setattr(compat.platform, "system", lambda: "Windows")
    monkeypatch.setattr(compat.importlib, "import_module", lambda name: fake)
    assert compat._enumerate_hkcr(("Apwn.Document",)) == [
        ("Apwn.Document.39", "64-bit"),
        ("Apwn.Document.40.0", "64-bit"),
    ]


def test_registry_enumeration_is_empty_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(compat.platform, "system", lambda: "Linux")
    assert compat._enumerate_hkcr(("Apwn.Document",)) == []


def test_aspen_discovery_deduplicates_views_and_sorts_newest_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASPENOPS_PROGID", raising=False)
    monkeypatch.setattr(
        compat,
        "_enumerate_hkcr",
        lambda prefixes: [
            ("Apwn.Document.39", "64-bit"),
            ("Apwn.Document.40.0", "32-bit"),
            ("Apwn.Document.40.0", "64-bit"),
            ("Apwn.Document.invalid", "64-bit"),
        ],
    )
    candidates = compat.discover_aspen_plus_candidates()
    assert [item.progid for item in candidates] == [
        "Apwn.Document.40.0",
        "Apwn.Document.39",
        "Apwn.Document",
    ]
    assert candidates[0].registry_view == "64-bit"
    assert candidates[-1].numeric_version == ()
    assert candidates[-1].to_dict()["numeric_version"] == []


def test_aspen_discovery_preserves_registered_unversioned_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASPENOPS_PROGID", raising=False)
    monkeypatch.setattr(
        compat,
        "_enumerate_hkcr",
        lambda prefixes: [("Apwn.Document", "64-bit")],
    )
    candidates = compat.discover_aspen_plus_candidates()
    assert len(candidates) == 1
    assert candidates[0].registry_view == "64-bit"


def test_hysys_discovery_and_compatibility_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASPENOPS_HYSYS_PROGID", raising=False)
    monkeypatch.setattr(
        compat,
        "_enumerate_hkcr",
        lambda prefixes: [
            ("HYSYS.Application.14", "32-bit"),
            ("HYSYS.Application.15", "64-bit"),
            ("HYSYS.Application.15", "32-bit"),
            ("HYSYS.Application.bad", "64-bit"),
        ],
    )
    candidates = compat.discover_hysys_candidates()
    assert [item.progid for item in candidates] == [
        "HYSYS.Application.15",
        "HYSYS.Application.14",
        "HYSYS.Application",
    ]
    monkeypatch.setattr(compat.platform, "platform", lambda: "test-platform")
    monkeypatch.setattr(
        compat,
        "discover_aspen_plus_candidates",
        lambda: [compat.ComCandidate("aspen_plus", "Apwn.Document", (), "fallback")],
    )
    monkeypatch.setattr(compat, "discover_hysys_candidates", lambda: candidates)
    report = compat.compatibility_report()
    assert report["platform"] == "test-platform"
    assert report["aspen_plus"][0]["progid"] == "Apwn.Document"
    assert report["hysys"][0]["numeric_version"] == [15]
    assert "newest-first" in report["strategy"]


def test_pinned_candidates_are_returned_without_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASPENOPS_PROGID", "Apwn.Document.99.1")
    monkeypatch.setenv("ASPENOPS_HYSYS_PROGID", "HYSYS.Application.88")
    monkeypatch.setattr(
        compat,
        "_enumerate_hkcr",
        lambda prefixes: pytest.fail("registry should not be enumerated"),
    )
    aspen = compat.discover_aspen_plus_candidates()[0]
    hysys = compat.discover_hysys_candidates()[0]
    assert aspen.pinned and aspen.numeric_version == (99, 1)
    assert hysys.pinned and hysys.numeric_version == (88,)


def test_conversion_finiteness_and_constraint_operator_edges() -> None:
    temperature = resolved_node("temperature", unit="C")
    assert _converted(True, temperature, "K") is True
    assert _converted("stable", temperature, "K") == "stable"
    assert _converted(0.0, temperature, "K") == pytest.approx(273.15)
    assert _finite(True)
    assert _finite("stable")
    assert _finite(1.5)
    assert not _finite(float("nan"))
    assert not _finite(object())

    cases = [
        ("<", 10.0, 10.0, 0.5, 0.5),
        ("<=", 10.0, 11.0, 0.5, 0.5),
        (">", 10.0, 10.0, 0.5, 0.5),
        (">=", 10.0, 9.0, 0.5, 0.5),
        ("==", 10.0, 11.0, 0.5, 0.5),
    ]
    for operator, limit, actual, tolerance, expected in cases:
        spec = ConstraintSpec(
            key="value",
            identifiers={},
            operator=operator,  # type: ignore[arg-type]
            value=limit,
            tolerance=tolerance,
        )
        assert _constraint_violation(spec, actual) == pytest.approx(expected)


class EvaluationBackend(SimulatorBackend):
    name = "mock"

    def __init__(
        self,
        values: dict[str, Any],
        run_info: dict[str, Any] | None = None,
    ) -> None:
        self.values = dict(values)
        self.run_info = run_info or {
            "engine_returned": True,
            "convergence_state": "converged",
            "converged": True,
        }
        self.reinitialize_calls = 0
        self.run_error: BaseException | None = None
        self.transaction_error: WriteTransactionError | None = None

    def open(self, model_path: Path, *, visible: bool = False) -> None:
        return None

    def close(self) -> None:
        return None

    def reinitialize(self) -> None:
        self.reinitialize_calls += 1

    def write(self, node: ResolvedNode, value: Any) -> None:
        self.values[node.key] = value

    def read(self, node: ResolvedNode) -> Any:
        return self.values[node.key]

    def bulk_write(self, items: list[tuple[ResolvedNode, Any]]) -> None:
        if self.transaction_error is not None:
            raise self.transaction_error
        for node, value in items:
            self.write(node, value)

    def run(self) -> dict[str, Any]:
        if self.run_error is not None:
            raise self.run_error
        return dict(self.run_info)

    def runtime_identity(self) -> dict[str, Any]:
        return {"backend": self.name, "case": "evaluation-test"}


def request(*, warm_start: bool = False) -> EvaluationRequest:
    return EvaluationRequest(
        model_path="model.json",
        registry_path="registry.json",
        backend="mock",
        writes=(),
        reads=(),
        reset_mode="warm_start" if warm_start else "reinitialize",
    )


def failure_plan() -> EvaluationPlan:
    output_node = resolved_node("output", unit="fraction")
    constraint_node = resolved_node("constraint", unit="1")
    inlet_node = resolved_node("inlet", unit="kg/h")
    outlet_node = resolved_node("outlet", unit="kg/h")
    read = VariableRead("output", {}, "fraction", required=True)
    constraint = ConstraintSpec(
        key="constraint",
        identifiers={},
        operator=">=",
        value=10.0,
        name="minimum",
    )
    inlet = BalanceTerm("inlet", {}, 1.0, "kg/h")
    outlet = BalanceTerm("outlet", {}, -1.0, "kg/h")
    balance = BalanceSpec(
        name="mass",
        terms=(inlet, outlet),
        expected=0.0,
        abs_tol=0.0,
        rel_tol=0.0,
        floor=1.0,
    )
    return EvaluationPlan(
        writes=(),
        unique_reads=(output_node, constraint_node, inlet_node, outlet_node),
        output_bindings=(
            OutputBinding(read, output_node, "output", "output"),
        ),
        constraints=(
            CompiledConstraint(constraint, constraint_node, "constraint"),
        ),
        balances=(
            CompiledBalance(
                balance,
                (
                    CompiledBalanceTerm(inlet, inlet_node, "inlet"),
                    CompiledBalanceTerm(outlet, outlet_node, "outlet"),
                ),
            ),
        ),
        physical_identity={},
        estimated_io=IOEstimate(0, 0, 4, 4, 0),
    )


def empty_plan() -> EvaluationPlan:
    return EvaluationPlan(
        writes=(),
        unique_reads=(),
        output_bindings=(),
        constraints=(),
        balances=(),
        physical_identity={},
        estimated_io=IOEstimate(0, 0, 0, 0, 0),
    )


def test_evaluation_combines_output_constraint_balance_and_engine_failures() -> None:
    backend = EvaluationBackend(
        {
            "output": float("nan"),
            "constraint": 5.0,
            "inlet": 10.0,
            "outlet": 4.0,
        },
        {
            "engine_returned": False,
            "convergence_state": "unknown",
            "converged": False,
        },
    )
    result = evaluate(
        backend,
        object(),  # type: ignore[arg-type]
        request(warm_start=True),
        worker_id=7,
        plan=failure_plan(),
    )
    assert result.ok is False
    assert result.communication_ok is True
    assert result.engine_ok is False
    assert result.converged is False
    assert result.feasible is False
    assert result.worker_id == 7
    assert result.violations == [
        "non_finite_required_output:output",
        "constraint_failed:minimum",
        "balance_failed:mass",
        "engine_did_not_return",
        "simulator_not_converged:unknown",
    ]
    assert result.diagnostics["state_trace"] == [
        "received",
        "plan_compiled",
        "warm_start",
        "writes_committed",
        "engine_returned",
        "outputs_read",
        "verified",
    ]
    assert result.diagnostics["total_constraint_violation"] == pytest.approx(5.0)
    assert result.balance_residuals["mass"]["residual"] == pytest.approx(6.0)
    assert result.balance_residuals["mass"]["passed"] == 0.0
    assert backend.reinitialize_calls == 0


def test_evaluation_reinitializes_and_accepts_empty_success_plan() -> None:
    backend = EvaluationBackend({})
    result = evaluate(
        backend,
        object(),  # type: ignore[arg-type]
        request(),
        plan=empty_plan(),
    )
    assert result.ok is True
    assert result.values == {}
    assert result.violations == []
    assert backend.reinitialize_calls == 1
    assert result.diagnostics["runtime"]["case"] == "evaluation-test"


@pytest.mark.parametrize("state", [TransactionState.ROLLED_BACK, TransactionState.TAINTED])
def test_evaluation_surfaces_write_transaction_state(
    state: TransactionState,
) -> None:
    backend = EvaluationBackend({})
    backend.transaction_error = WriteTransactionError(state, RuntimeError("write failed"))
    result = evaluate(
        backend,
        object(),  # type: ignore[arg-type]
        request(),
        plan=empty_plan(),
    )
    assert result.ok is False
    assert result.violations == [f"write_transaction:{state.value}"]
    assert result.diagnostics["transaction_state"] == state.value
    assert result.diagnostics["worker_tainted"] is (state is TransactionState.TAINTED)
    assert result.diagnostics["state_trace"][-1] == "failed"


def test_evaluation_surfaces_generic_execution_error() -> None:
    backend = EvaluationBackend({})
    backend.run_error = ValueError("solver exploded")
    result = evaluate(
        backend,
        object(),  # type: ignore[arg-type]
        request(),
        plan=empty_plan(),
    )
    assert result.ok is False
    assert result.communication_ok is False
    assert result.violations == ["execution_error:ValueError"]
    assert result.diagnostics["exception"] == "solver exploded"
    assert result.diagnostics["state_trace"][-1] == "failed"
