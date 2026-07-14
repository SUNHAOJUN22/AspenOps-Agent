import pytest

from aspenops_nexus.solver_status import assess_convergence


@pytest.mark.parametrize("idle", [True, False, None])
def test_no_status_evidence_is_never_convergence(idle: bool | None) -> None:
    assessment = assess_convergence([], idle)
    assert assessment.converged is False
    assert assessment.explicit is False
    assert assessment.reason == "missing_explicit_positive_status"


def test_unknown_numeric_status_is_not_convergence() -> None:
    assessment = assess_convergence([1, 8], True)
    assert assessment.converged is False
    assert assessment.explicit is False


def test_explicit_positive_status_requires_engine_not_busy() -> None:
    assert assess_convergence(["Run completed successfully"], True).converged is True
    assessment = assess_convergence(["Run completed successfully"], False)
    assert assessment.converged is False
    assert assessment.reason == "engine_not_idle_after_positive_status"


def test_explicit_negative_status_overrides_positive_substring() -> None:
    assessment = assess_convergence(["Run incomplete; not converged"], True)
    assert assessment.converged is False
    assert assessment.explicit is True
    assert assessment.reason == "explicit_negative_status"


def test_blank_status_values_are_ignored() -> None:
    assessment = assess_convergence([None, "", "   ", "Converged"], True)
    assert assessment.raw_status == ("Converged",)
    assert assessment.converged is True
