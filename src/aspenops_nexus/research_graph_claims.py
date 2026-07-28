from __future__ import annotations

from .research_common import Maturity, ObjectRef, _MATURITY_RANK
from .research_graph_support import GraphContext
from .research_objects import Assumption, Validation


def lower_maturity(left: Maturity, right: Maturity) -> Maturity:
    return left if _MATURITY_RANK[left] <= _MATURITY_RANK[right] else right


def higher_maturity(values: list[Maturity]) -> Maturity:
    result: Maturity = "STRUCTURE_ONLY"
    for value in values:
        if _MATURITY_RANK[value] > _MATURITY_RANK[result]:
            result = value
    return result


def validate_claims(ctx: GraphContext, validation_ceiling: Maturity) -> Maturity:
    document = ctx.document
    if document.validations:
        computed_ceiling = lower_maturity(document.study.claim_ceiling, validation_ceiling)
    else:
        computed_ceiling = lower_maturity(
            document.study.claim_ceiling,
            "SOURCE_CASE_REPRODUCED",
        )

    for claim in document.claims:
        owner = ObjectRef("claim", claim.claim_id)
        for index, ref in enumerate(claim.evidence_refs):
            ctx.resolve(ref, owner=owner, path=f"claim.evidence_refs[{index}]")
        validations: list[Validation] = []
        for index, ref in enumerate(claim.validation_refs):
            value = ctx.resolve_typed(
                ref,
                "validation",
                Validation,
                owner=owner,
                path=f"claim.validation_refs[{index}]",
                code="claim_validation_type",
                label="Claim validation_refs",
            )
            if value is not None:
                validations.append(value)
        assumptions: list[Assumption] = []
        for index, ref in enumerate(claim.assumption_refs):
            value = ctx.resolve_typed(
                ref,
                "assumption",
                Assumption,
                owner=owner,
                path=f"claim.assumption_refs[{index}]",
                code="claim_assumption_type",
                label="Claim assumption_refs",
            )
            if value is not None:
                assumptions.append(value)

        if (
            document.study.purpose == "source_reproduction"
            and _MATURITY_RANK[claim.maturity]
            > _MATURITY_RANK["SOURCE_CASE_REPRODUCED"]
        ):
            ctx.add(
                "error",
                "source_reproduction_claim_ceiling",
                "Source-reproduction Study cannot support independent validation maturity",
                owner,
                "claim.maturity",
            )
        if _MATURITY_RANK[claim.maturity] > _MATURITY_RANK[document.study.claim_ceiling]:
            ctx.add(
                "error",
                "claim_exceeds_study_ceiling",
                "Claim maturity exceeds Study claim_ceiling",
                owner,
                "claim.maturity",
            )
        if (
            claim.claim_type not in {"structure", "source_reproduction"}
            and not any(item.status == "passed" for item in validations)
        ):
            ctx.add(
                "error",
                "claim_requires_passed_validation",
                "Claim requires at least one passed Validation",
                owner,
                "claim.validation_refs",
            )
        passed_ceilings = [
            item.claim_ceiling_result for item in validations if item.status == "passed"
        ]
        linked_ceiling = higher_maturity(passed_ceilings)
        if _MATURITY_RANK[claim.maturity] > _MATURITY_RANK[linked_ceiling]:
            ctx.add(
                "error",
                "claim_exceeds_validation_ceiling",
                "Claim maturity exceeds linked Validation claim ceiling",
                owner,
                "claim.maturity",
            )

        propagated = set(claim.limitations) | set(claim.prohibited_interpretations)
        for assumption in assumptions:
            missing = sorted(set(assumption.claim_restrictions) - propagated)
            if missing:
                ctx.add(
                    "error",
                    "claim_missing_assumption_restriction",
                    "Claim does not propagate Assumption restrictions: " + "; ".join(missing),
                    owner,
                    "claim.limitations",
                )
            if (
                assumption.risk == "critical"
                and assumption.status in {"proposed", "challenged", "unresolved"}
                and claim.maturity != "STRUCTURE_ONLY"
            ):
                ctx.add(
                    "error",
                    "claim_blocked_by_critical_assumption",
                    "Critical unresolved Assumption limits Claim to STRUCTURE_ONLY",
                    owner,
                    "claim.maturity",
                )

        if claim.maturity == "LICENSED_ENGINEERING_REVIEWED":
            _validate_licensed_claim(ctx, owner, validations)
        if claim.claim_sha256 is not None and claim.claim_sha256 != claim.computed_sha256():
            ctx.add(
                "error",
                "claim_hash_mismatch",
                "claim_sha256 does not match canonical Claim content",
                owner,
                "claim.claim_sha256",
            )

    _validate_lifecycle(ctx)
    return computed_ceiling


def _validate_licensed_claim(
    ctx: GraphContext,
    owner: ObjectRef,
    validations: list[Validation],
) -> None:
    policy = ctx.document.study.backend_policy
    allowed_raw = policy.get("allowed_backends")
    allowed = {str(value) for value in allowed_raw} if isinstance(allowed_raw, list) else set()
    if not policy.get("require_licensed_windows") or not allowed.intersection(
        {"aspen_plus", "hysys"}
    ):
        ctx.add(
            "error",
            "licensed_claim_backend_policy",
            "Licensed claim requires licensed real-simulator backend policy",
            owner,
            "study.backend_policy",
        )
    approved = any(
        item.status == "passed"
        and item.execution_policy.get("backend") in {"aspen_plus", "hysys"}
        and item.execution_policy.get("engineering_approved") is True
        for item in validations
    )
    if not approved:
        ctx.add(
            "error",
            "licensed_claim_missing_engineering_validation",
            "Licensed claim requires passed real-simulator Validation with approval",
            owner,
            "claim.validation_refs",
        )


def _validate_lifecycle(ctx: GraphContext) -> None:
    document = ctx.document
    lifecycle = document.study.lifecycle_state
    accepted = any(item.status == "accepted" for item in document.calibrations)
    passed = any(item.status == "passed" for item in document.validations)
    ready_claim = any(item.status in {"supported", "qualified"} for item in document.claims)
    calibration_states = {"calibrated", "validation_ready", "validated", "claim_ready"}
    if lifecycle in calibration_states and not accepted:
        ctx.add(
            "error",
            "study_lifecycle_missing_calibration",
            "Study lifecycle requires an accepted Calibration",
            ObjectRef("study", document.study.study_id),
            "study.lifecycle_state",
        )
    if lifecycle in {"validated", "claim_ready"} and not passed:
        ctx.add(
            "error",
            "study_lifecycle_missing_validation",
            "Study lifecycle requires a passed Validation",
            ObjectRef("study", document.study.study_id),
            "study.lifecycle_state",
        )
    if lifecycle == "claim_ready" and not ready_claim:
        ctx.add(
            "error",
            "study_lifecycle_missing_claim",
            "claim_ready Study requires a supported or qualified Claim",
            ObjectRef("study", document.study.study_id),
            "study.lifecycle_state",
        )
