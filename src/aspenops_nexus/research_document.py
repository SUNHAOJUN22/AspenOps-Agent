from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Literal, cast

from .research_common import (
    RESEARCH_SCHEMA,
    ArtifactRef,
    IssueSeverity,
    Maturity,
    ObjectRef,
    ResearchObjectType,
    ResearchValidationError,
    SemanticBinding,
    SourceRef,
    _mapping,
    _reject_unknown,
    _sequence,
    _text,
    canonical_hash,
)
from .research_objects import (
    Assumption,
    Calibration,
    Claim,
    Dataset,
    DatasetVariableRef,
    Parameter,
    Study,
    Target,
    Validation,
)


@dataclass(frozen=True, slots=True)
class ResearchIssue:
    severity: IssueSeverity
    code: str
    message: str
    object_ref: ObjectRef | None = None
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.object_ref is not None:
            result["object_ref"] = self.object_ref.to_dict()
        if self.path is not None:
            result["path"] = self.path
        return result


@dataclass(frozen=True, slots=True)
class ResearchValidationReport:
    status: Literal["PASS", "FAIL"]
    issues: tuple[ResearchIssue, ...]
    object_counts: dict[str, int]
    canonical_sha256: str
    computed_claim_ceiling: Maturity

    @property
    def ok(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "aspenops.research-validation/v1",
            "status": self.status,
            "issues": [item.to_dict() for item in self.issues],
            "object_counts": dict(self.object_counts),
            "canonical_sha256": self.canonical_sha256,
            "computed_claim_ceiling": self.computed_claim_ceiling,
        }


@dataclass(frozen=True, slots=True)
class ResearchStudyDocument:
    schema: str
    study: Study
    datasets: tuple[Dataset, ...] = ()
    targets: tuple[Target, ...] = ()
    parameters: tuple[Parameter, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    calibrations: tuple[Calibration, ...] = ()
    validations: tuple[Validation, ...] = ()
    claims: tuple[Claim, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchStudyDocument:
        mapping = _mapping(data, "research document")
        _reject_unknown(
            mapping,
            {
                "schema",
                "study",
                "datasets",
                "targets",
                "parameters",
                "assumptions",
                "calibrations",
                "validations",
                "claims",
            },
            "research document",
        )
        schema = _text(mapping.get("schema"), "research document.schema")
        if schema != RESEARCH_SCHEMA:
            raise ResearchValidationError(f"research document.schema must be {RESEARCH_SCHEMA}")
        return cls(
            schema=schema,
            study=Study.from_dict(_mapping(mapping.get("study"), "research document.study")),
            datasets=tuple(
                Dataset.from_dict(_mapping(item, f"datasets[{index}]"))
                for index, item in enumerate(_sequence(mapping.get("datasets", []), "datasets"))
            ),
            targets=tuple(
                Target.from_dict(_mapping(item, f"targets[{index}]"))
                for index, item in enumerate(_sequence(mapping.get("targets", []), "targets"))
            ),
            parameters=tuple(
                Parameter.from_dict(_mapping(item, f"parameters[{index}]"))
                for index, item in enumerate(_sequence(mapping.get("parameters", []), "parameters"))
            ),
            assumptions=tuple(
                Assumption.from_dict(_mapping(item, f"assumptions[{index}]"))
                for index, item in enumerate(
                    _sequence(mapping.get("assumptions", []), "assumptions")
                )
            ),
            calibrations=tuple(
                Calibration.from_dict(_mapping(item, f"calibrations[{index}]"))
                for index, item in enumerate(
                    _sequence(mapping.get("calibrations", []), "calibrations")
                )
            ),
            validations=tuple(
                Validation.from_dict(_mapping(item, f"validations[{index}]"))
                for index, item in enumerate(
                    _sequence(mapping.get("validations", []), "validations")
                )
            ),
            claims=tuple(
                Claim.from_dict(_mapping(item, f"claims[{index}]"))
                for index, item in enumerate(_sequence(mapping.get("claims", []), "claims"))
            ),
        )

    @classmethod
    def load(cls, path: str | Path) -> ResearchStudyDocument:
        source = Path(path).expanduser().resolve()
        payload = source.read_bytes()
        from . import research as public_research

        limit = public_research.MAX_DOCUMENT_BYTES
        if len(payload) > limit:
            raise ResearchValidationError(f"research document exceeds {limit} bytes")
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResearchValidationError(f"invalid research JSON: {exc}") from exc
        return cls.from_dict(_mapping(value, "research document"))

    def to_dict(self) -> dict[str, Any]:
        def normalize(value: Any) -> Any:
            if isinstance(value, ObjectRef):
                return value.to_dict()
            if isinstance(value, ArtifactRef):
                return value.to_dict()
            if isinstance(value, SemanticBinding):
                return value.to_dict()
            if isinstance(value, SourceRef):
                return value.to_dict()
            if isinstance(value, DatasetVariableRef):
                return {"dataset_id": value.dataset_id, "variable": value.variable}
            if hasattr(value, "__dataclass_fields__"):
                result: dict[str, Any] = {}
                for item in fields(value):
                    result[item.name] = normalize(getattr(value, item.name))
                return result
            if isinstance(value, dict):
                return {str(key): normalize(item) for key, item in value.items()}
            if isinstance(value, tuple | list):
                return [normalize(item) for item in value]
            return value

        return {
            "schema": self.schema,
            "study": normalize(self.study),
            "datasets": [normalize(item) for item in self.datasets],
            "targets": [normalize(item) for item in self.targets],
            "parameters": [normalize(item) for item in self.parameters],
            "assumptions": [normalize(item) for item in self.assumptions],
            "calibrations": [normalize(item) for item in self.calibrations],
            "validations": [normalize(item) for item in self.validations],
            "claims": [normalize(item) for item in self.claims],
        }

    def canonical_sha256(self) -> str:
        return canonical_hash(self.to_dict())

    def _objects(self) -> dict[tuple[ResearchObjectType, str], Any]:
        result: dict[tuple[ResearchObjectType, str], Any] = {
            ("study", self.study.study_id): self.study
        }
        collections: tuple[tuple[ResearchObjectType, tuple[Any, ...], str], ...] = (
            ("dataset", self.datasets, "dataset_id"),
            ("target", self.targets, "target_id"),
            ("parameter", self.parameters, "parameter_id"),
            ("assumption", self.assumptions, "assumption_id"),
            ("calibration", self.calibrations, "calibration_id"),
            ("validation", self.validations, "validation_id"),
            ("claim", self.claims, "claim_id"),
        )
        for object_type, collection, id_field in collections:
            for item in collection:
                identifier = cast(str, getattr(item, id_field))
                key = (object_type, identifier)
                if key in result:
                    raise ResearchValidationError(f"duplicate research object: {identifier}")
                result[key] = item
        return result

    def validate(self) -> ResearchValidationReport:
        from .research_graph import validate_document

        return validate_document(self)
