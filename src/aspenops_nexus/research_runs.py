from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, cast

from .research_common import (
    ArtifactRef,
    Maturity,
    ObjectRef,
    ResearchObjectType,
    ResearchValidationError,
    _MATURITY_RANK,
    _enum,
    _id,
    _json_object,
    _mapping,
    _refs,
    _reject_unknown,
    _sequence,
    _strings,
)


@dataclass(frozen=True, slots=True)
class Calibration:
    calibration_id: str
    stage: str
    method: str
    dataset_refs: tuple[ObjectRef, ...]
    target_refs: tuple[ObjectRef, ...]
    parameter_refs: tuple[ObjectRef, ...]
    fixed_parameter_snapshot: ArtifactRef
    objective: dict[str, Any]
    constraints: tuple[dict[str, Any], ...]
    algorithm: dict[str, Any]
    initialization: dict[str, Any]
    execution_plan: dict[str, Any]
    data_split_proof: dict[str, Any]
    result_artifact: ArtifactRef | None
    diagnostics: dict[str, Any] | None
    acceptance_policy: dict[str, Any]
    status: str
    accepted_parameter_snapshot: ArtifactRef | None

    object_type: ClassVar[ResearchObjectType] = "calibration"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Calibration:
        mapping = _mapping(data, "calibration")
        _reject_unknown(
            mapping,
            {
                "calibration_id",
                "stage",
                "method",
                "dataset_refs",
                "target_refs",
                "parameter_refs",
                "fixed_parameter_snapshot",
                "objective",
                "constraints",
                "algorithm",
                "initialization",
                "execution_plan",
                "data_split_proof",
                "result_artifact",
                "diagnostics",
                "acceptance_policy",
                "status",
                "accepted_parameter_snapshot",
            },
            "calibration",
        )
        result_value = mapping.get("result_artifact")
        accepted_value = mapping.get("accepted_parameter_snapshot")
        status = _enum(
            mapping.get("status"),
            {
                "draft",
                "ready",
                "running",
                "converged",
                "nonconverged",
                "statistically_weak",
                "accepted",
                "rejected",
                "blocked",
            },
            "calibration.status",
        )
        result_artifact = (
            None
            if result_value is None
            else ArtifactRef.from_dict(
                _mapping(result_value, "calibration.result_artifact"),
                label="calibration.result_artifact",
            )
        )
        accepted_snapshot = (
            None
            if accepted_value is None
            else ArtifactRef.from_dict(
                _mapping(accepted_value, "calibration.accepted_parameter_snapshot"),
                label="calibration.accepted_parameter_snapshot",
            )
        )
        if status == "accepted" and accepted_snapshot is None:
            raise ResearchValidationError(
                "accepted calibration requires accepted_parameter_snapshot"
            )
        return cls(
            calibration_id=_id(
                mapping.get("calibration_id"), "calibration", "calibration.calibration_id"
            ),
            stage=_enum(
                mapping.get("stage"),
                {
                    "C0_data",
                    "C1_thermo",
                    "C2_production",
                    "C3_molecular_weight",
                    "C4_composition",
                    "C5_distribution",
                    "C6_polymer_specific",
                    "C7_dynamic_hybrid",
                },
                "calibration.stage",
            ),
            method=_enum(
                mapping.get("method"),
                {
                    "sensitivity",
                    "design_specification",
                    "data_fit",
                    "external_optimizer",
                    "manual_review",
                },
                "calibration.method",
            ),
            dataset_refs=_refs(
                mapping.get("dataset_refs", []),
                "calibration.dataset_refs",
                nonempty=True,
            ),
            target_refs=_refs(
                mapping.get("target_refs", []),
                "calibration.target_refs",
                nonempty=True,
            ),
            parameter_refs=_refs(
                mapping.get("parameter_refs", []),
                "calibration.parameter_refs",
                nonempty=True,
            ),
            fixed_parameter_snapshot=ArtifactRef.from_dict(
                _mapping(
                    mapping.get("fixed_parameter_snapshot"),
                    "calibration.fixed_parameter_snapshot",
                ),
                label="calibration.fixed_parameter_snapshot",
            ),
            objective=_json_object(mapping.get("objective"), "calibration.objective"),
            constraints=tuple(
                _json_object(item, f"calibration.constraints[{index}]")
                for index, item in enumerate(
                    _sequence(mapping.get("constraints", []), "calibration.constraints")
                )
            ),
            algorithm=_json_object(mapping.get("algorithm"), "calibration.algorithm"),
            initialization=_json_object(
                mapping.get("initialization"), "calibration.initialization"
            ),
            execution_plan=_json_object(
                mapping.get("execution_plan"), "calibration.execution_plan"
            ),
            data_split_proof=_json_object(
                mapping.get("data_split_proof"), "calibration.data_split_proof"
            ),
            result_artifact=result_artifact,
            diagnostics=(
                None
                if mapping.get("diagnostics") is None
                else _json_object(mapping["diagnostics"], "calibration.diagnostics")
            ),
            acceptance_policy=_json_object(
                mapping.get("acceptance_policy"), "calibration.acceptance_policy"
            ),
            status=status,
            accepted_parameter_snapshot=accepted_snapshot,
        )


@dataclass(frozen=True, slots=True)
class Validation:
    validation_id: str
    validation_type: str
    dataset_refs: tuple[ObjectRef, ...]
    target_refs: tuple[ObjectRef, ...]
    parameter_snapshot: ArtifactRef
    model_snapshot: ArtifactRef
    registry_snapshot: ArtifactRef
    execution_policy: dict[str, Any]
    acceptance_policy: dict[str, Any]
    coverage_envelope: dict[str, Any]
    results_artifact: ArtifactRef | None
    leakage_check: dict[str, Any]
    robustness_summary: dict[str, Any] | None
    blockers: tuple[str, ...]
    status: str
    claim_ceiling_result: Maturity

    object_type: ClassVar[ResearchObjectType] = "validation"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Validation:
        mapping = _mapping(data, "validation")
        _reject_unknown(
            mapping,
            {
                "validation_id",
                "validation_type",
                "dataset_refs",
                "target_refs",
                "parameter_snapshot",
                "model_snapshot",
                "registry_snapshot",
                "execution_policy",
                "acceptance_policy",
                "coverage_envelope",
                "results_artifact",
                "leakage_check",
                "robustness_summary",
                "blockers",
                "status",
                "claim_ceiling_result",
            },
            "validation",
        )
        result_value = mapping.get("results_artifact")
        result_artifact = (
            None
            if result_value is None
            else ArtifactRef.from_dict(
                _mapping(result_value, "validation.results_artifact"),
                label="validation.results_artifact",
            )
        )
        blockers = _strings(mapping.get("blockers", []), "validation.blockers")
        status = _enum(
            mapping.get("status"),
            {
                "draft",
                "ready",
                "running",
                "passed",
                "failed",
                "incomplete",
                "blocked",
                "superseded",
            },
            "validation.status",
        )
        if status == "passed" and (result_artifact is None or blockers):
            raise ResearchValidationError(
                "passed validation requires results_artifact and no blockers"
            )
        return cls(
            validation_id=_id(
                mapping.get("validation_id"), "validation", "validation.validation_id"
            ),
            validation_type=_enum(
                mapping.get("validation_type"),
                {
                    "heldout_grade",
                    "heldout_time",
                    "cross_reactor",
                    "stress_test",
                    "out_of_domain",
                    "repeatability",
                    "conservation",
                    "dynamic",
                    "external",
                },
                "validation.validation_type",
            ),
            dataset_refs=_refs(
                mapping.get("dataset_refs", []),
                "validation.dataset_refs",
                nonempty=True,
            ),
            target_refs=_refs(
                mapping.get("target_refs", []),
                "validation.target_refs",
                nonempty=True,
            ),
            parameter_snapshot=ArtifactRef.from_dict(
                _mapping(mapping.get("parameter_snapshot"), "validation.parameter_snapshot"),
                label="validation.parameter_snapshot",
            ),
            model_snapshot=ArtifactRef.from_dict(
                _mapping(mapping.get("model_snapshot"), "validation.model_snapshot"),
                label="validation.model_snapshot",
            ),
            registry_snapshot=ArtifactRef.from_dict(
                _mapping(mapping.get("registry_snapshot"), "validation.registry_snapshot"),
                label="validation.registry_snapshot",
            ),
            execution_policy=_json_object(
                mapping.get("execution_policy"), "validation.execution_policy"
            ),
            acceptance_policy=_json_object(
                mapping.get("acceptance_policy"), "validation.acceptance_policy"
            ),
            coverage_envelope=_json_object(
                mapping.get("coverage_envelope"), "validation.coverage_envelope"
            ),
            results_artifact=result_artifact,
            leakage_check=_json_object(
                mapping.get("leakage_check"), "validation.leakage_check"
            ),
            robustness_summary=(
                None
                if mapping.get("robustness_summary") is None
                else _json_object(
                    mapping["robustness_summary"], "validation.robustness_summary"
                )
            ),
            blockers=blockers,
            status=status,
            claim_ceiling_result=cast(
                Maturity,
                _enum(
                    mapping.get("claim_ceiling_result"),
                    set(_MATURITY_RANK),
                    "validation.claim_ceiling_result",
                ),
            ),
        )
