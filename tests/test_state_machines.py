import pytest

from aspenops_nexus.state_machines import (
    ALL_STATE_MACHINES,
    APPROVAL_REQUEST,
    JOB,
    StateTransitionError,
)


@pytest.mark.parametrize("spec", ALL_STATE_MACHINES, ids=lambda spec: spec.name)
def test_state_machine_structure_is_complete(spec) -> None:
    spec.validate_complete()
    assert spec.initial in spec.states
    assert spec.terminal <= spec.states
    assert not any(source in spec.terminal for source, _target in spec.transitions)


@pytest.mark.parametrize("spec", ALL_STATE_MACHINES, ids=lambda spec: spec.name)
def test_all_declared_transitions_are_legal(spec) -> None:
    for source, target in spec.transitions:
        spec.require_transition(source, target)


def test_terminal_job_states_cannot_restart() -> None:
    for terminal in JOB.terminal:
        with pytest.raises(StateTransitionError):
            JOB.require_transition(terminal, "RUNNING")


def test_idempotent_reapplication_is_explicitly_allowed() -> None:
    JOB.require_transition("PENDING", "PENDING")
    APPROVAL_REQUEST.require_transition("APPROVED", "APPROVED")


def test_approval_is_invalidated_after_bound_inputs_change() -> None:
    assert APPROVAL_REQUEST.can_transition("APPROVED", "INVALIDATED")
    assert not APPROVAL_REQUEST.can_transition("APPROVED", "PENDING")
