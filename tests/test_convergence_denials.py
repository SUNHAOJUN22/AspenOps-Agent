"""Negative completion evidence must dominate an embedded positive keyword."""

from __future__ import annotations

import pytest

from aspenops_nexus.convergence import ConvergenceState, IdleObservation, classify_convergence


@pytest.mark.parametrize(
    "message",
    [
        "not all blocks converged",
        "Not all equations have converged",
        "no blocks converged",
        "none of the recycle blocks converged",
        "run completed; 0 blocks converged",
        "zero streams converged",
        "converged: false",
        "CONVERGED = NO",
        "converged = 0",
        "run completed; convergence: false",
    ],
)
def test_denied_convergence_is_never_accepted(message: str) -> None:
    evidence = classify_convergence(
        engine_returned=True,
        idle=IdleObservation(ConvergenceState.UNKNOWN, True, 0.2, 3),
        status_nodes=[{"path": "status", "value": message}],
        messages=[],
        source="declared-test-fixture",
    )
    assert evidence.state is ConvergenceState.NOT_CONVERGED
    assert evidence.negative_markers
    assert evidence.status_nodes[0]["value"] == message


@pytest.mark.parametrize(
    "message",
    [
        "All blocks converged; 0 errors",
        "Converged: true; no errors",
        "Converged = 1; errors: 0",
        "All equations have converged successfully",
    ],
)
def test_explicit_positive_evidence_remains_accepted(message: str) -> None:
    evidence = classify_convergence(
        engine_returned=True,
        idle=IdleObservation(ConvergenceState.UNKNOWN, True, 0.2, 3),
        status_nodes=[],
        messages=[message],
        source="declared-test-fixture",
    )
    assert evidence.state is ConvergenceState.CONVERGED
    assert not evidence.negative_markers
