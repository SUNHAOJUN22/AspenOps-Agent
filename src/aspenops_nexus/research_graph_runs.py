from __future__ import annotations

from .research_common import Maturity, ObjectRef, _MATURITY_RANK
from .research_graph_support import GraphContext
from .research_objects import Dataset, Parameter, Target


def validate_runs(ctx: GraphContext) -> Maturity:
    document = ctx.document
    datasets_by_id = {item.dataset_id: item for item in document.datasets}
    calibrations_by_id = {item.calibration_id: item for item in document.calibrations}
    calibration_dataset_ids: set[str] = set()
    validation_dataset_ids: set[str] = set()

    for calibration in document.calibrations:
        owner = ObjectRef("calibration", calibration.calibration_id)
        estimated_count = 0
        for index, ref in enumerate(calibration.dataset_refs):
            dataset = ctx.resolve_typed(
                ref,
                "dataset",
                Dataset,
                owner=owner,
                path=f"calibration.dataset_refs[{index}]",
                code="calibration_dataset_type",
                label="Calibration dataset_refs",
            )
            if dataset is not None:
                calibration_dataset_ids.add(dataset.dataset_id)
                if dataset.role != "calibration":
                    ctx.add(
                        "error",
                        "calibration_dataset_role",
                        f"Calibration uses Dataset with role={dataset.role}",
                        owner,
                        f"calibration.dataset_refs[{index}]",
                    )
        for index, ref in enumerate(calibration.target_refs):
            target = ctx.resolve_typed(
                ref,
                "target",
                Target,
                owner=owner,
                path=f"calibration.target_refs[{index}]",
                code="calibration_target_type",
                label="Calibration target_refs",
            )
            if target is not None and target.role not in {"fit", "acceptance", "diagnostic"}:
                ctx.add(
                    "error",
                    "calibration_target_role",
                    f"Calibration cannot use Target with role={target.role}",
                    owner,
                    f"calibration.target_refs[{index}]",
                )
        for index, ref in enumerate(calibration.parameter_refs):
            parameter = ctx.resolve_typed(
                ref,
                "parameter",
                Parameter,
                owner=owner,
                path=f"calibration.parameter_refs[{index}]",
                code="calibration_parameter_type",
                label="Calibration parameter_refs",
            )
            if parameter is not None and parameter.mode == "estimated":
                estimated_count += 1
        if (
            calibration.method in {"data_fit", "design_specification", "external_optimizer"}
            and estimated_count == 0
        ):
            ctx.add(
                "error",
                "calibration_no_estimated_parameter",
                f"{calibration.method} requires at least one estimated Parameter",
                owner,
                "calibration.parameter_refs",
            )
        accepted = calibration.accepted_parameter_snapshot
        if accepted is not None and accepted.producer != owner:
            ctx.add(
                "error",
                "calibration_snapshot_producer",
                "Accepted parameter snapshot must identify its Calibration as producer",
                owner,
                "calibration.accepted_parameter_snapshot.producer",
            )

    ceiling: Maturity = "STRUCTURE_ONLY"
    for validation in document.validations:
        owner = ObjectRef("validation", validation.validation_id)
        for index, ref in enumerate(validation.dataset_refs):
            dataset = ctx.resolve_typed(
                ref,
                "dataset",
                Dataset,
                owner=owner,
                path=f"validation.dataset_refs[{index}]",
                code="validation_dataset_type",
                label="Validation dataset_refs",
            )
            if dataset is not None:
                validation_dataset_ids.add(dataset.dataset_id)
                if dataset.role not in {"validation", "stress_test"}:
                    ctx.add(
                        "error",
                        "validation_dataset_role",
                        f"Validation uses Dataset with role={dataset.role}",
                        owner,
                        f"validation.dataset_refs[{index}]",
                    )
        for index, ref in enumerate(validation.target_refs):
            ctx.resolve_typed(
                ref,
                "target",
                Target,
                owner=owner,
                path=f"validation.target_refs[{index}]",
                code="validation_target_type",
                label="Validation target_refs",
            )

        producer = validation.parameter_snapshot.producer
        if producer is None or producer.object_type != "calibration":
            ctx.add(
                "error",
                "validation_snapshot_missing_calibration",
                "Validation parameter snapshot must be produced by a Calibration",
                owner,
                "validation.parameter_snapshot.producer",
            )
        else:
            calibration = calibrations_by_id.get(producer.object_id)
            if calibration is None:
                ctx.add(
                    "error",
                    "validation_calibration_missing",
                    f"Validation references missing Calibration: {producer.object_id}",
                    owner,
                    "validation.parameter_snapshot.producer",
                )
            elif calibration.status != "accepted":
                ctx.add(
                    "error",
                    "validation_calibration_not_accepted",
                    "Validation must use an accepted Calibration",
                    owner,
                    "validation.parameter_snapshot.producer",
                )
            elif calibration.accepted_parameter_snapshot is None or (
                calibration.accepted_parameter_snapshot.sha256
                != validation.parameter_snapshot.sha256
            ):
                ctx.add(
                    "error",
                    "validation_snapshot_mismatch",
                    "Validation parameter snapshot does not match accepted Calibration snapshot",
                    owner,
                    "validation.parameter_snapshot.sha256",
                )
        if validation.model_snapshot.sha256 != document.study.model_ref.sha256:
            ctx.add(
                "error",
                "validation_model_snapshot_mismatch",
                "Validation model snapshot does not match Study model_ref",
                owner,
                "validation.model_snapshot.sha256",
            )
        if validation.registry_snapshot.sha256 != document.study.registry_ref.sha256:
            ctx.add(
                "error",
                "validation_registry_snapshot_mismatch",
                "Validation registry snapshot does not match Study registry_ref",
                owner,
                "validation.registry_snapshot.sha256",
            )
        if validation.status == "passed" and (
            _MATURITY_RANK[validation.claim_ceiling_result] > _MATURITY_RANK[ceiling]
        ):
            ceiling = validation.claim_ceiling_result

    _validate_leakage(
        ctx,
        datasets_by_id,
        calibration_dataset_ids,
        validation_dataset_ids,
    )
    return ceiling


def _validate_leakage(
    ctx: GraphContext,
    datasets_by_id: dict[str, Dataset],
    calibration_ids: set[str],
    validation_ids: set[str],
) -> None:
    study_ref = ObjectRef("study", ctx.document.study.study_id)
    for dataset_id in sorted(calibration_ids & validation_ids):
        ctx.add(
            "error",
            "calibration_validation_dataset_leakage",
            f"Dataset is used for both Calibration and Validation: {dataset_id}",
            study_ref,
            "study.calibration_validation_policy",
        )
    calibration_datasets = [datasets_by_id[item] for item in calibration_ids]
    validation_datasets = [datasets_by_id[item] for item in validation_ids]
    for calibration in calibration_datasets:
        for validation in validation_datasets:
            if calibration.data_artifact.sha256 == validation.data_artifact.sha256:
                ctx.add(
                    "error",
                    "calibration_validation_artifact_leakage",
                    "Calibration and Validation use the same immutable data artifact",
                    study_ref,
                    "study.calibration_validation_policy",
                )
            if (
                calibration.split_group is not None
                and calibration.split_group == validation.split_group
            ):
                ctx.add(
                    "error",
                    "calibration_validation_split_group_leakage",
                    "Calibration and Validation share the same split_group",
                    study_ref,
                    "study.calibration_validation_policy",
                )
            if (
                calibration.record_set_sha256 is not None
                and calibration.record_set_sha256 == validation.record_set_sha256
            ):
                ctx.add(
                    "error",
                    "calibration_validation_record_leakage",
                    "Calibration and Validation share the same record-set digest",
                    study_ref,
                    "study.calibration_validation_policy",
                )
