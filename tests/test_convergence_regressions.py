from __future__ import annotations

import pytest

from aspenops_nexus.convergence import (
    ConvergenceState,
    IdleObservation,
    classify_convergence,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("not successful", ConvergenceState.NOT_CONVERGED),
        ("not_successful", ConvergenceState.NOT_CONVERGED),
        ("unsuccessful", ConvergenceState.NOT_CONVERGED),
        ("not ok", ConvergenceState.NOT_CONVERGED),
        ("0 errors; completed successfully", ConvergenceState.CONVERGED),
        ("errors: 0; converged", ConvergenceState.CONVERGED),
        ("no errors; converged", ConvergenceState.CONVERGED),
        ("10 errors; completed successfully", ConvergenceState.NOT_CONVERGED),
        ("errors: 0.5; converged", ConvergenceState.NOT_CONVERGED),
        ("errors: 0e3; converged", ConvergenceState.NOT_CONVERGED),
        ("0 errors; fatal error; completed", ConvergenceState.NOT_CONVERGED),
        ("0 errors", ConvergenceState.UNKNOWN),
    ],
)
def test_status_text_preserves_negation_and_error_counts(
    text: str, expected: ConvergenceState
) -> None:
    evidence = classify_convergence(
        engine_returned=True,
        idle=IdleObservation(ConvergenceState.UNKNOWN, True, 0.0, 1),
        status_nodes=[],
        messages=[text],
        source="synthetic-regression",
    )
    assert evidence.state is expected
    assert evidence.messages == (text,)
