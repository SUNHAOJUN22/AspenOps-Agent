from __future__ import annotations

from dataclasses import dataclass
from typing import Final


class StateTransitionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StateMachineSpec:
    name: str
    initial: str
    states: frozenset[str]
    transitions: frozenset[tuple[str, str]]
    terminal: frozenset[str]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("State machine name must not be blank")
        if self.initial not in self.states:
            raise ValueError(f"{self.name}: initial state is not declared")
        if not self.terminal.issubset(self.states):
            raise ValueError(f"{self.name}: terminal states must be declared")
        for source, target in self.transitions:
            if source not in self.states or target not in self.states:
                raise ValueError(
                    f"{self.name}: transition {source}->{target} references unknown state"
                )
            if source in self.terminal:
                raise ValueError(
                    f"{self.name}: terminal state {source} cannot have outgoing transitions"
                )
            if source == target:
                raise ValueError(
                    f"{self.name}: idempotency must be handled explicitly, not as a self-transition"
                )

    def can_transition(self, source: str, target: str) -> bool:
        return (source, target) in self.transitions

    def require_transition(self, source: str, target: str) -> None:
        if source == target:
            return
        if not self.can_transition(source, target):
            raise StateTransitionError(
                f"Illegal {self.name} transition: {source!r} -> {target!r}"
            )

    def validate_complete(self) -> None:
        for state in self.states - self.terminal:
            if not any(source == state for source, _target in self.transitions):
                raise ValueError(f"{self.name}: nonterminal state {state!r} has no exit")


JOB: Final = StateMachineSpec(
    name="Job",
    initial="PENDING",
    states=frozenset(
        {
            "PENDING",
            "CLAIMED",
            "RUNNING",
            "SUCCEEDED",
            "FAILED",
            "CANCELLED",
            "TIMED_OUT",
            "INTERRUPTED",
        }
    ),
    transitions=frozenset(
        {
            ("PENDING", "CLAIMED"),
            ("PENDING", "CANCELLED"),
            ("CLAIMED", "RUNNING"),
            ("CLAIMED", "FAILED"),
            ("CLAIMED", "CANCELLED"),
            ("CLAIMED", "TIMED_OUT"),
            ("CLAIMED", "INTERRUPTED"),
            ("RUNNING", "SUCCEEDED"),
            ("RUNNING", "FAILED"),
            ("RUNNING", "CANCELLED"),
            ("RUNNING", "TIMED_OUT"),
            ("RUNNING", "INTERRUPTED"),
        }
    ),
    terminal=frozenset({"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT", "INTERRUPTED"}),
)

WORKER: Final = StateMachineSpec(
    name="Worker",
    initial="NEW",
    states=frozenset(
        {"NEW", "STARTING", "READY", "BUSY", "RECYCLING", "STOPPING", "STOPPED", "FAILED"}
    ),
    transitions=frozenset(
        {
            ("NEW", "STARTING"),
            ("STARTING", "READY"),
            ("STARTING", "FAILED"),
            ("READY", "BUSY"),
            ("READY", "RECYCLING"),
            ("READY", "STOPPING"),
            ("BUSY", "READY"),
            ("BUSY", "RECYCLING"),
            ("BUSY", "FAILED"),
            ("RECYCLING", "STOPPING"),
            ("STOPPING", "STOPPED"),
            ("STOPPING", "FAILED"),
        }
    ),
    terminal=frozenset({"STOPPED", "FAILED"}),
)

SESSION: Final = StateMachineSpec(
    name="Session",
    initial="CREATED",
    states=frozenset({"CREATED", "OPENING", "OPEN", "CLOSING", "CLOSED", "FAILED"}),
    transitions=frozenset(
        {
            ("CREATED", "OPENING"),
            ("OPENING", "OPEN"),
            ("OPENING", "FAILED"),
            ("OPEN", "CLOSING"),
            ("OPEN", "FAILED"),
            ("CLOSING", "CLOSED"),
            ("CLOSING", "FAILED"),
        }
    ),
    terminal=frozenset({"CLOSED", "FAILED"}),
)

ASPEN_CASE: Final = StateMachineSpec(
    name="AspenCase",
    initial="STAGED",
    states=frozenset(
        {
            "STAGED",
            "OPENING",
            "OPEN",
            "SOLVING",
            "SOLVED",
            "VALIDATING",
            "CERTIFIED",
            "FAILED",
            "CLOSED",
        }
    ),
    transitions=frozenset(
        {
            ("STAGED", "OPENING"),
            ("OPENING", "OPEN"),
            ("OPENING", "FAILED"),
            ("OPEN", "SOLVING"),
            ("OPEN", "CLOSED"),
            ("SOLVING", "SOLVED"),
            ("SOLVING", "FAILED"),
            ("SOLVED", "VALIDATING"),
            ("SOLVED", "SOLVING"),
            ("VALIDATING", "CERTIFIED"),
            ("VALIDATING", "FAILED"),
            ("CERTIFIED", "CLOSED"),
        }
    ),
    terminal=frozenset({"FAILED", "CLOSED"}),
)

CERTIFICATION_RUN: Final = StateMachineSpec(
    name="CertificationRun",
    initial="PENDING",
    states=frozenset({"PENDING", "RUNNING", "PASSED", "FAILED", "BLOCKED"}),
    transitions=frozenset(
        {
            ("PENDING", "RUNNING"),
            ("PENDING", "BLOCKED"),
            ("RUNNING", "PASSED"),
            ("RUNNING", "FAILED"),
            ("RUNNING", "BLOCKED"),
        }
    ),
    terminal=frozenset({"PASSED", "FAILED", "BLOCKED"}),
)

EVIDENCE_BUNDLE: Final = StateMachineSpec(
    name="EvidenceBundle",
    initial="BUILDING",
    states=frozenset({"BUILDING", "SEALED", "VERIFIED", "CORRUPT"}),
    transitions=frozenset(
        {
            ("BUILDING", "SEALED"),
            ("BUILDING", "CORRUPT"),
            ("SEALED", "VERIFIED"),
            ("SEALED", "CORRUPT"),
        }
    ),
    terminal=frozenset({"VERIFIED", "CORRUPT"}),
)

SURROGATE_MODEL: Final = StateMachineSpec(
    name="SurrogateModel",
    initial="DRAFT",
    states=frozenset(
        {"DRAFT", "VALIDATING", "ACTIVE", "DRIFTED", "BLOCKED", "RETIRED"}
    ),
    transitions=frozenset(
        {
            ("DRAFT", "VALIDATING"),
            ("VALIDATING", "ACTIVE"),
            ("VALIDATING", "BLOCKED"),
            ("ACTIVE", "DRIFTED"),
            ("ACTIVE", "BLOCKED"),
            ("ACTIVE", "RETIRED"),
            ("DRIFTED", "VALIDATING"),
            ("DRIFTED", "BLOCKED"),
            ("BLOCKED", "VALIDATING"),
            ("BLOCKED", "RETIRED"),
        }
    ),
    terminal=frozenset({"RETIRED"}),
)

APPROVAL_REQUEST: Final = StateMachineSpec(
    name="ApprovalRequest",
    initial="PENDING",
    states=frozenset({"PENDING", "APPROVED", "REJECTED", "EXPIRED", "INVALIDATED"}),
    transitions=frozenset(
        {
            ("PENDING", "APPROVED"),
            ("PENDING", "REJECTED"),
            ("PENDING", "EXPIRED"),
            ("APPROVED", "INVALIDATED"),
        }
    ),
    terminal=frozenset({"REJECTED", "EXPIRED", "INVALIDATED"}),
)

ALL_STATE_MACHINES: Final = (
    JOB,
    WORKER,
    SESSION,
    ASPEN_CASE,
    CERTIFICATION_RUN,
    EVIDENCE_BUNDLE,
    SURROGATE_MODEL,
    APPROVAL_REQUEST,
)
