import math
from types import SimpleNamespace

import pytest

from aspenops_nexus.backends.aspen_plus import _configured_delay
from aspenops_nexus.backends.hysys import HysysBackend


def test_hysys_idle_is_not_reported_as_convergence() -> None:
    backend = HysysBackend()
    backend.case = SimpleNamespace(Solver=SimpleNamespace(IsSolving=False, CanSolve=True))
    result = backend.run()

    assert result["engine_returned"] is True
    assert result["converged"] is False
    evidence = result["convergence_evidence"]
    assert evidence["reason"] == "missing_explicit_positive_status"
    assert evidence["engine_idle"] is True


@pytest.mark.parametrize("value", ["nan", "inf", "-1"])
def test_aspen_delays_reject_nonfinite_or_negative_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("ASPENOPS_TEST_DELAY", value)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        _configured_delay("ASPENOPS_TEST_DELAY", 0.0)


def test_aspen_delay_accepts_zero_and_finite_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASPENOPS_TEST_DELAY", "0")
    assert _configured_delay("ASPENOPS_TEST_DELAY", 2.0) == 0.0
    monkeypatch.setenv("ASPENOPS_TEST_DELAY", "0.25")
    assert math.isclose(_configured_delay("ASPENOPS_TEST_DELAY", 2.0), 0.25)
