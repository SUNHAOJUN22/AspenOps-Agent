from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_POSITIVE_MARKERS = (
    "converged",
    "completed",
    "complete",
    "success",
    "successful",
    "ready",
)
_NEGATIVE_MARKERS = (
    "not converged",
    "unconverged",
    "failed",
    "failure",
    "error",
    "incomplete",
    "aborted",
    "stopped",
)


@dataclass(frozen=True, slots=True)
class ConvergenceAssessment:
    converged: bool
    explicit: bool
    positive_evidence: tuple[str, ...]
    negative_evidence: tuple[str, ...]
    raw_status: tuple[str, ...]
    engine_idle: bool | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "converged": self.converged,
            "explicit": self.explicit,
            "positive_evidence": list(self.positive_evidence),
            "negative_evidence": list(self.negative_evidence),
            "raw_status": list(self.raw_status),
            "engine_idle": self.engine_idle,
            "reason": self.reason,
        }


def assess_convergence(
    status_values: list[Any] | tuple[Any, ...],
    engine_idle: bool | None,
) -> ConvergenceAssessment:
    raw_status = tuple(str(value).strip() for value in status_values if value is not None)
    normalized = tuple(value.casefold() for value in raw_status if value)
    positive = tuple(
        raw
        for raw, text in zip(raw_status, normalized, strict=True)
        if any(marker in text for marker in _POSITIVE_MARKERS)
    )
    negative = tuple(
        raw
        for raw, text in zip(raw_status, normalized, strict=True)
        if any(marker in text for marker in _NEGATIVE_MARKERS)
    )
    explicit = bool(positive or negative)
    converged = bool(positive) and not negative and engine_idle is not False
    if negative:
        reason = "explicit_negative_status"
    elif not positive:
        reason = "missing_explicit_positive_status"
    elif engine_idle is False:
        reason = "engine_not_idle_after_positive_status"
    else:
        reason = "explicit_positive_status"
    return ConvergenceAssessment(
        converged=converged,
        explicit=explicit,
        positive_evidence=positive,
        negative_evidence=negative,
        raw_status=raw_status,
        engine_idle=engine_idle,
        reason=reason,
    )
