from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Route = Literal["SURROGATE", "ASPEN", "BLOCKED", "APPROVAL_REQUIRED"]
DriftState = Literal["OK", "WARNING", "BLOCK"]


@dataclass(frozen=True, slots=True)
class TwinSignals:
    data_quality_ok: bool
    freshness_ok: bool
    state_estimation_ok: bool
    surrogate_compatible: bool
    in_applicability_domain: bool
    drift: DriftState
    uncertainty: float
    uncertainty_limit: float
    constraints_feasible: bool
    near_constraint_boundary: bool
    approval_required: bool
    approval_valid: bool
    aspen_available: bool

    def __post_init__(self) -> None:
        if self.drift not in {"OK", "WARNING", "BLOCK"}:
            raise ValueError(f"Unsupported drift state: {self.drift}")
        if self.uncertainty < 0.0 or self.uncertainty_limit < 0.0:
            raise ValueError("Uncertainty and its limit must be nonnegative")


@dataclass(frozen=True, slots=True)
class RouteDecision:
    route: Route
    reason: str
    trace: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _fallback(signals: TwinSignals, reason: str, trace: list[str]) -> RouteDecision:
    if signals.aspen_available:
        return RouteDecision("ASPEN", reason, tuple(trace))
    return RouteDecision("BLOCKED", f"{reason}; Aspen fallback unavailable", tuple(trace))


def route_twin(signals: TwinSignals) -> RouteDecision:
    trace: list[str] = []
    trace.append("Data Quality")
    if not signals.data_quality_ok:
        return RouteDecision("BLOCKED", "data quality gate failed", tuple(trace))
    trace.append("Freshness")
    if not signals.freshness_ok:
        return RouteDecision("BLOCKED", "data freshness gate failed", tuple(trace))
    trace.append("State Estimation")
    if not signals.state_estimation_ok:
        return RouteDecision("BLOCKED", "state estimation gate failed", tuple(trace))
    trace.append("Surrogate Compatibility")
    if not signals.surrogate_compatible:
        return _fallback(signals, "surrogate manifest is incompatible", trace)
    trace.append("Applicability Domain")
    if not signals.in_applicability_domain:
        return _fallback(signals, "surrogate input is outside applicability domain", trace)
    trace.append("Drift")
    if signals.drift == "BLOCK":
        return RouteDecision("BLOCKED", "severe surrogate drift", tuple(trace))
    if signals.drift == "WARNING":
        return _fallback(signals, "surrogate drift warning", trace)
    trace.append("Uncertainty")
    if signals.uncertainty > signals.uncertainty_limit:
        return _fallback(signals, "surrogate uncertainty exceeds limit", trace)
    trace.append("Constraints")
    if not signals.constraints_feasible:
        return RouteDecision("BLOCKED", "physical or operating constraints are violated", tuple(trace))
    if signals.near_constraint_boundary:
        return RouteDecision("APPROVAL_REQUIRED", "constraints are near a governed boundary", tuple(trace))
    trace.append("Approval")
    if signals.approval_required and not signals.approval_valid:
        return RouteDecision("APPROVAL_REQUIRED", "valid bound approval is missing", tuple(trace))
    trace.append("Route")
    return RouteDecision("SURROGATE", "all surrogate governance gates passed", tuple(trace))
