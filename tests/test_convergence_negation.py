"""A stopped engine and an embedded success word cannot override negation."""

import pytest

from aspenops_nexus.convergence import (
    ConvergenceState,
    IdleObservation,
    classify_convergence,
)


@pytest.mark.parametrize(
    "message",
    [
        "Calculation has not yet converged.",
        "Calculation is not fully converged.",
        "The run is not completely converged.",
        "Calculation did not converge; execution completed.",
        "Calculation never converged; run completed.",
        "A non-converged result was returned.",
        "A nonconverged result was returned; run completed.",
        "An unconverged result was returned; run completed.",
        "Unable to converge; execution completed.",
        "Convergence not yet achieved; execution completed.",
        "Convergence not reached; execution completed.",
        "NOT_YET_CONVERGED",
    ],
)
@pytest.mark.parametrize("location", ["message", "status_node"])
def test_negated_convergence_is_never_accepted(message: str, location: str) -> None:
    evidence = classify_convergence(
        engine_returned=True,
        idle=IdleObservation(ConvergenceState.UNKNOWN, True, 0.2, 3),
        status_nodes=[{"value": message}] if location == "status_node" else [],
        messages=[message] if location == "message" else [],
        source="negation-regression",
    )
    assert evidence.state is ConvergenceState.NOT_CONVERGED
    assert "not_converged" in evidence.negative_markers
    assert message in str(evidence.to_dict())


@pytest.mark.parametrize(
    "message",
    [
        "The result is not only converged but also balanced.",
        "The calculation fully converged with no errors.",
        "Execution completed and converged; errors: 0",
    ],
)
def test_unambiguous_success_is_preserved(message: str) -> None:
    evidence = classify_convergence(
        engine_returned=True,
        idle=IdleObservation(ConvergenceState.UNKNOWN, True, 0.2, 3),
        status_nodes=[],
        messages=[message],
        source="negation-regression",
    )
    assert evidence.state is ConvergenceState.CONVERGED
