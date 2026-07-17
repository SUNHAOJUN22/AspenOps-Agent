from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ConvergenceState(StrEnum):
    CONVERGED = "converged"
    NOT_CONVERGED = "not_converged"
    RUNNING = "running"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class IdleObservation:
    state: ConvergenceState
    engine_idle: bool | None
    elapsed_s: float
    samples: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ConvergenceEvidence:
    state: ConvergenceState
    engine_returned: bool
    engine_idle: bool | None
    status_nodes: tuple[dict[str, Any], ...]
    messages: tuple[str, ...]
    source: str
    elapsed_s: float
    samples: int
    positive_markers: tuple[str, ...] = ()
    negative_markers: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "engine_returned": self.engine_returned,
            "engine_idle": self.engine_idle,
            "status_nodes": [dict(item) for item in self.status_nodes],
            "messages": list(self.messages),
            "source": self.source,
            "elapsed_s": self.elapsed_s,
            "samples": self.samples,
            "positive_markers": list(self.positive_markers),
            "negative_markers": list(self.negative_markers),
            "error": self.error,
        }


_NEGATIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("not_converged", re.compile(r"\bnot[\s_-]+converged\b", re.IGNORECASE)),
    ("not_completed", re.compile(r"\bnot[\s_-]+completed?\b", re.IGNORECASE)),
    ("failed", re.compile(r"\bfailed?\b|\bfailure\b", re.IGNORECASE)),
    ("error", re.compile(r"\berror(?:s)?\b", re.IGNORECASE)),
    ("fatal", re.compile(r"\bfatal\b", re.IGNORECASE)),
    ("aborted", re.compile(r"\baborted?\b", re.IGNORECASE)),
    ("incomplete", re.compile(r"\bincomplete\b", re.IGNORECASE)),
)

_POSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("converged", re.compile(r"\bconverged\b", re.IGNORECASE)),
    ("completed", re.compile(r"\bcompleted?\b", re.IGNORECASE)),
    ("successful", re.compile(r"\bsuccess(?:ful(?:ly)?)?\b", re.IGNORECASE)),
    ("ok", re.compile(r"\bok\b", re.IGNORECASE)),
)


def poll_engine_idle(
    read_running: Callable[[], bool | None],
    *,
    timeout_s: float,
    poll_interval_s: float,
    stable_samples: int,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> IdleObservation:
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    if poll_interval_s <= 0:
        raise ValueError("poll_interval_s must be positive")
    if stable_samples <= 0:
        raise ValueError("stable_samples must be positive")

    started = clock()
    samples = 0
    consecutive_idle = 0
    observed_running = False
    observed_known_state = False
    while True:
        try:
            running = read_running()
        except Exception as exc:
            return IdleObservation(
                state=ConvergenceState.ERROR,
                engine_idle=None,
                elapsed_s=max(0.0, clock() - started),
                samples=samples,
                error=f"{type(exc).__name__}: {exc}",
            )
        samples += 1
        if running is None:
            consecutive_idle = 0
        else:
            observed_known_state = True
            if running:
                observed_running = True
                consecutive_idle = 0
            else:
                consecutive_idle += 1
                if consecutive_idle >= stable_samples:
                    return IdleObservation(
                        state=ConvergenceState.UNKNOWN,
                        engine_idle=True,
                        elapsed_s=max(0.0, clock() - started),
                        samples=samples,
                    )

        elapsed = max(0.0, clock() - started)
        if elapsed >= timeout_s:
            if not observed_known_state:
                state = ConvergenceState.UNKNOWN
                engine_idle = None
            elif observed_running:
                state = ConvergenceState.TIMEOUT
                engine_idle = False
            else:
                state = ConvergenceState.UNKNOWN
                engine_idle = None
            return IdleObservation(
                state=state,
                engine_idle=engine_idle,
                elapsed_s=elapsed,
                samples=samples,
            )
        sleeper(min(poll_interval_s, timeout_s - elapsed))


def _markers(text: str, patterns: Iterable[tuple[str, re.Pattern[str]]]) -> tuple[str, ...]:
    return tuple(name for name, pattern in patterns if pattern.search(text))


def classify_convergence(
    *,
    engine_returned: bool,
    idle: IdleObservation,
    status_nodes: Iterable[dict[str, Any]],
    messages: Iterable[str],
    source: str,
) -> ConvergenceEvidence:
    normalized_nodes = tuple(dict(item) for item in status_nodes)
    normalized_messages = tuple(str(item) for item in messages)
    evidence_text = " | ".join(
        [str(item.get("value", "")) for item in normalized_nodes]
        + list(normalized_messages)
    )
    negative = _markers(evidence_text, _NEGATIVE_PATTERNS)
    positive = _markers(evidence_text, _POSITIVE_PATTERNS)

    if not engine_returned:
        state = ConvergenceState.ERROR
    elif idle.state in {ConvergenceState.TIMEOUT, ConvergenceState.ERROR}:
        state = idle.state
    elif negative:
        state = ConvergenceState.NOT_CONVERGED
    elif positive and idle.engine_idle is True:
        state = ConvergenceState.CONVERGED
    elif idle.engine_idle is False:
        state = ConvergenceState.RUNNING
    else:
        state = ConvergenceState.UNKNOWN

    return ConvergenceEvidence(
        state=state,
        engine_returned=engine_returned,
        engine_idle=idle.engine_idle,
        status_nodes=normalized_nodes,
        messages=normalized_messages,
        source=source,
        elapsed_s=idle.elapsed_s,
        samples=idle.samples,
        positive_markers=positive,
        negative_markers=negative,
        error=idle.error,
    )
