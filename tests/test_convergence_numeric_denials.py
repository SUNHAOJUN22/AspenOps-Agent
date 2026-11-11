"""Explicit zero/false status tokens must dominate embedded completion words."""

from __future__ import annotations

import pytest

from aspenops_nexus.convergence import (
    ConvergenceEvidence,
    ConvergenceState,
    IdleObservation,
    classify_convergence,
)


def _classify(text: str, location: str = "message") -> ConvergenceEvidence:
    return classify_convergence(
        engine_returned=True,
        idle=IdleObservation(ConvergenceState.UNKNOWN, True, 0.2, 3),
        status_nodes=[{"path": "status", "value": text}] if location == "status_node" else [],
        messages=[text] if location == "message" else [],
        source="synthetic-status-token-regression",
    )


@pytest.mark.parametrize(
    "status",
    [
        "Converged = 0.0",
        "Converged: -0.0",
        "Converged is +0.0",
        "CONVERGENCE = 0e0",
        "converged: 0E+5",
        "convergence is -0e-400",
        "converged = +00.000e999999",
        "convergence = .0",
        "converged = -.0e-03",
        "converged = 00.",
    ],
)
@pytest.mark.parametrize("location", ["message", "status_node"])
def test_lexical_zero_status_is_denied(status: str, location: str) -> None:
    text = f"Run completed; {status}"
    evidence = _classify(text, location)
    assert evidence.state is ConvergenceState.NOT_CONVERGED
    assert "convergence_denied" in evidence.negative_markers
    assert evidence.messages == ((text,) if location == "message" else ())
    assert evidence.status_nodes == (
        ({"path": "status", "value": text},) if location == "status_node" else ()
    )


@pytest.mark.parametrize("token", ["false", "NO", "0.0", "-0.0", "0e0", "-0e-400"])
@pytest.mark.parametrize("suffix", [".", ". Next step.", ".\nNext step.", '."', ".)"])
@pytest.mark.parametrize("location", ["message", "status_node"])
def test_denial_followed_by_sentence_punctuation_is_preserved(
    token: str, suffix: str, location: str
) -> None:
    text = f"Run completed; converged = {token}{suffix}"
    evidence = _classify(text, location)
    assert evidence.state is ConvergenceState.NOT_CONVERGED
    assert "convergence_denied" in evidence.negative_markers
    assert evidence.messages == ((text,) if location == "message" else ())
    assert evidence.status_nodes == (
        ({"path": "status", "value": text},) if location == "status_node" else ()
    )


@pytest.mark.parametrize("token", ["0.1", "0.01", "-0.1", "+0.2", "0.1e-400", "-0.1e-400"])
def test_nonzero_tokens_are_not_reclassified_by_float_underflow(token: str) -> None:
    evidence = _classify(f"Run completed; converged = {token}")
    assert evidence.state is ConvergenceState.CONVERGED
    assert "convergence_denied" not in evidence.negative_markers


@pytest.mark.parametrize(
    "token",
    [
        "falsehood",
        "nobody",
        "false.value",
        "0.0e1foo",
        "0.0.1",
        "0..1",
        "0e-400units",
        "0.0-e4",
    ],
)
def test_denial_match_does_not_consume_a_longer_token_prefix(token: str) -> None:
    evidence = _classify(f"Run completed; converged = {token}")
    assert evidence.state is ConvergenceState.CONVERGED
    assert "convergence_denied" not in evidence.negative_markers
