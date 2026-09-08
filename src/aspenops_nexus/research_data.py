from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Literal, cast

from .research_common import (
    _SEMANTIC_KEY_PATTERN,
    ArtifactRef,
    ObjectRef,
    ResearchObjectType,
    ResearchValidationError,
    SemanticBinding,
    _boolean,
    _enum,
    _id,
    _json_object,
    _mapping,
    _optional_sha256,
    _optional_text,
    _refs,
    _reject_unknown,
    _sequence,
    _strings,
    _text,
)


@dataclass(frozen=True, slots=True)
class DatasetVariable:
    name: str
    semantic_key: str
    unit: str
    data_type: Literal["number", "integer", "string", "boolean", "datetime"]
    role: Literal["input", "target", "context", "quality_flag", "record_id"]
    missing_policy: Literal["reject", "allow", "impute_declared"]

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str) -> DatasetVariable:
        mapping = _mapping(data, label)
        _reject_unknown(
            mapping,
            {"name", "semantic_key", "unit", "data_type", "role", "missing_policy"},
            label,
        )
        semantic_key = _text(mapping.get("semantic_key"), f"{label}.semantic_key")
        if _SEMANTIC_KEY_PATTERN.fullmatch(semantic_key) is None:
            raise ResearchValidationError(f"{label}.semantic_key is not a safe Registry key")
        return cls(
            name=_text(mapping.get("name"), f"{label}.name"),
            semantic_key=semantic_key,
            unit=_text(mapping.get("unit"), f"{label}.unit"),
            data_type=cast(
                Literal["number", "integer", "string", "boolean", "datetime"],
                _enum(
                    mapping.get("data_type"),
                    {"number", "integer", "string", "boolean", "datetime"},
                    f"{label}.data_type",
                ),
            ),
            role=cast(
                Literal["input", "target", "context", "quality_flag", "record_id"],
                _enum(
                    mapping.get("role"),
                    {"input", "target", "context", "quality_flag", "record_id"},
                    f"{label}.role",
                ),
            ),
            missing_policy=cast(
                Literal["reject", "allow", "impute_declared"],
                _enum(
                    mapping.get("missing_policy", "reject"),
                    {"reject", "allow", "impute_declared"},
                    f"{label}.missing_policy",
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class Dataset:
    dataset_id: str
    kind: str
    role: str
    structure: str
    data_artifact: ArtifactRef
    variables: tuple[DatasetVariable, ...]
    record_identity: tuple[str, ...]
    measurement_uncertainty: dict[str, Any]
    quality_flags: dict[str, Any]
    confidentiality: str
    operating_envelope: dict[str, Any] | None = None
    reconciliation: dict[str, Any] | None = None
    lineage: tuple[ObjectRef, ...] = ()
    sampling: dict[str, Any] | None = None
    split_group: str | None = None
    record_set_sha256: str | None = None

    object_type: ClassVar[ResearchObjectType] = "dataset"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Dataset:
        mapping = _mapping(data, "dataset")
        _reject_unknown(
            mapping,
            {
                "dataset_id",
                "kind",
                "role",
                "structure",
                "data_artifact",
                "variables",
                "record_identity",
                "operating_envelope",
                "measurement_uncertainty",
                "reconciliation",
                "quality_flags",
                "lineage",
                "sampling",
                "split_group",
                "record_set_sha256",
                "confidentiality",
            },
            "dataset",
        )
        variables = tuple(
            DatasetVariable.from_dict(
                _mapping(item, f"dataset.variables[{index}]"),
                label=f"dataset.variables[{index}]",
            )
            for index, item in enumerate(
                _sequence(mapping.get("variables", []), "dataset.variables")
            )
        )
        if not variables:
            raise ResearchValidationError("dataset.variables must not be empty")
        names = [item.name for item in variables]
        if len(set(names)) != len(names):
            raise ResearchValidationError("dataset variable names must be unique")
        record_identity = _strings(
            mapping.get("record_identity", []),
            "dataset.record_identity",
            nonempty=True,
        )
        missing_ids = sorted(set(record_identity) - set(names))
        if missing_ids:
            raise ResearchValidationError(
                "dataset.record_identity contains undeclared variables: " + ", ".join(missing_ids)
            )
        return cls(
            dataset_id=_id(mapping.get("dataset_id"), "dataset", "dataset.dataset_id"),
            kind=_enum(
                mapping.get("kind"),
                {"plant", "laboratory", "literature", "simulation", "soft_sensor", "derived"},
                "dataset.kind",
            ),
            role=_enum(
                mapping.get("role"),
                {"calibration", "validation", "stress_test", "context", "screening"},
                "dataset.role",
            ),
            structure=_enum(
                mapping.get("structure"),
                {"point", "time_series", "profile", "distribution", "matrix", "event_log"},
                "dataset.structure",
            ),
            data_artifact=ArtifactRef.from_dict(
                _mapping(mapping.get("data_artifact"), "dataset.data_artifact"),
                label="dataset.data_artifact",
            ),
            variables=variables,
            record_identity=record_identity,
            operating_envelope=(
                None
                if mapping.get("operating_envelope") is None
                else _json_object(mapping["operating_envelope"], "dataset.operating_envelope")
            ),
            measurement_uncertainty=_json_object(
                mapping.get("measurement_uncertainty"),
                "dataset.measurement_uncertainty",
            ),
            reconciliation=(
                None
                if mapping.get("reconciliation") is None
                else _json_object(mapping["reconciliation"], "dataset.reconciliation")
            ),
            quality_flags=_json_object(mapping.get("quality_flags"), "dataset.quality_flags"),
            lineage=_refs(mapping.get("lineage", []), "dataset.lineage"),
            sampling=(
                None
                if mapping.get("sampling") is None
                else _json_object(mapping["sampling"], "dataset.sampling")
            ),
            split_group=_optional_text(mapping.get("split_group"), "dataset.split_group"),
            record_set_sha256=_optional_sha256(
                mapping.get("record_set_sha256"), "dataset.record_set_sha256"
            ),
            confidentiality=_enum(
                mapping.get("confidentiality"),
                {"public", "internal", "restricted", "confidential"},
                "dataset.confidentiality",
            ),
        )


@dataclass(frozen=True, slots=True)
class DatasetVariableRef:
    dataset_id: str
    variable: str

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str) -> DatasetVariableRef:
        mapping = _mapping(data, label)
        _reject_unknown(mapping, {"dataset_id", "variable"}, label)
        return cls(
            dataset_id=_id(mapping.get("dataset_id"), "dataset", f"{label}.dataset_id"),
            variable=_text(mapping.get("variable"), f"{label}.variable"),
        )


@dataclass(frozen=True, slots=True)
class Target:
    target_id: str
    category: str
    semantic_binding: SemanticBinding
    dataset_binding: DatasetVariableRef | None
    measurement_kind: str
    unit: str
    transform: str | dict[str, Any] | None
    uncertainty_ref: str | None
    role: str
    acceptance: dict[str, Any]
    dependencies: tuple[ObjectRef, ...]
    expected_trend: dict[str, Any] | None
    stage: str
    required: bool
    claim_relevance: tuple[str, ...]

    object_type: ClassVar[ResearchObjectType] = "target"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Target:
        mapping = _mapping(data, "target")
        _reject_unknown(
            mapping,
            {
                "target_id",
                "category",
                "semantic_binding",
                "dataset_binding",
                "measurement_kind",
                "unit",
                "transform",
                "uncertainty_ref",
                "role",
                "acceptance",
                "dependencies",
                "expected_trend",
                "stage",
                "required",
                "claim_relevance",
            },
            "target",
        )
        transform_value = mapping.get("transform")
        if transform_value is None:
            transform: str | dict[str, Any] | None = None
        elif isinstance(transform_value, str):
            transform = _enum(
                transform_value,
                {"identity", "log", "log10", "standardize", "custom_declared"},
                "target.transform",
            )
        else:
            transform = _json_object(transform_value, "target.transform")
        binding_value = mapping.get("dataset_binding")
        binding = (
            None
            if binding_value is None
            else DatasetVariableRef.from_dict(
                _mapping(binding_value, "target.dataset_binding"),
                label="target.dataset_binding",
            )
        )
        semantic_binding = SemanticBinding.from_dict(
            _mapping(mapping.get("semantic_binding"), "target.semantic_binding"),
            label="target.semantic_binding",
        )
        if semantic_binding.access != "read":
            raise ResearchValidationError("target.semantic_binding.access must be read")
        return cls(
            target_id=_id(mapping.get("target_id"), "target", "target.target_id"),
            category=_enum(
                mapping.get("category"),
                {
                    "production",
                    "conversion",
                    "molecular_weight",
                    "composition",
                    "distribution",
                    "thermodynamics",
                    "dynamic",
                    "control",
                    "economics",
                    "integrity",
                },
                "target.category",
            ),
            semantic_binding=semantic_binding,
            dataset_binding=binding,
            measurement_kind=_enum(
                mapping.get("measurement_kind"),
                {"direct", "indirect", "correlated", "simulated", "soft_sensor", "derived"},
                "target.measurement_kind",
            ),
            unit=_text(mapping.get("unit"), "target.unit"),
            transform=transform,
            uncertainty_ref=_optional_text(
                mapping.get("uncertainty_ref"), "target.uncertainty_ref"
            ),
            role=_enum(
                mapping.get("role"),
                {"fit", "acceptance", "constraint", "diagnostic", "monitoring"},
                "target.role",
            ),
            acceptance=_json_object(mapping.get("acceptance"), "target.acceptance"),
            dependencies=_refs(mapping.get("dependencies", []), "target.dependencies"),
            expected_trend=(
                None
                if mapping.get("expected_trend") is None
                else _json_object(mapping["expected_trend"], "target.expected_trend")
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
                "target.stage",
            ),
            required=_boolean(mapping.get("required"), "target.required"),
            claim_relevance=_strings(mapping.get("claim_relevance", []), "target.claim_relevance"),
        )
