from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, cast

from .research_common import (
    ArtifactRef,
    Maturity,
    ObjectRef,
    ResearchObjectType,
    ResearchValidationError,
    _LIFECYCLE_RANK,
    _MATURITY_RANK,
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
    canonical_hash,
)


@dataclass(frozen=True, slots=True)
class Claim:
    claim_id: str
    statement: str
    claim_type: str
    maturity: Maturity
    scope: dict[str, Any]
    evidence_refs: tuple[ObjectRef, ...]
    validation_refs: tuple[ObjectRef, ...]
    assumption_refs: tuple[ObjectRef, ...]
    limitations: tuple[str, ...]
    prohibited_interpretations: tuple[str, ...]
    confidence_basis: dict[str, Any]
    review: dict[str, Any]
    status: str
    expires_at: str | None
    claim_sha256: str | None

    object_type: ClassVar[ResearchObjectType] = "claim"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Claim:
        mapping = _mapping(data, "claim")
        _reject_unknown(
            mapping,
            {
                "claim_id",
                "statement",
                "claim_type",
                "maturity",
                "scope",
                "evidence_refs",
                "validation_refs",
                "assumption_refs",
                "limitations",
                "prohibited_interpretations",
                "confidence_basis",
                "review",
                "status",
                "expires_at",
                "claim_sha256",
            },
            "claim",
        )
        return cls(
            claim_id=_id(mapping.get("claim_id"), "claim", "claim.claim_id"),
            statement=_text(mapping.get("statement"), "claim.statement"),
            claim_type=_enum(
                mapping.get("claim_type"),
                {
                    "structure",
                    "source_reproduction",
                    "parameter_estimate",
                    "predictive_performance",
                    "mechanism_support",
                    "optimization_recommendation",
                    "dynamic_control",
                    "engineering_qualification",
                },
                "claim.claim_type",
            ),
            maturity=cast(
                Maturity,
                _enum(mapping.get("maturity"), set(_MATURITY_RANK), "claim.maturity"),
            ),
            scope=_json_object(mapping.get("scope"), "claim.scope"),
            evidence_refs=_refs(
                mapping.get("evidence_refs", []), "claim.evidence_refs", nonempty=True
            ),
            validation_refs=_refs(
                mapping.get("validation_refs", []), "claim.validation_refs"
            ),
            assumption_refs=_refs(
                mapping.get("assumption_refs", []), "claim.assumption_refs"
            ),
            limitations=_strings(
                mapping.get("limitations", []), "claim.limitations", nonempty=True
            ),
            prohibited_interpretations=_strings(
                mapping.get("prohibited_interpretations", []),
                "claim.prohibited_interpretations",
                nonempty=True,
            ),
            confidence_basis=_json_object(
                mapping.get("confidence_basis"), "claim.confidence_basis"
            ),
            review=_json_object(mapping.get("review"), "claim.review"),
            status=_enum(
                mapping.get("status"),
                {
                    "proposed",
                    "supported",
                    "qualified",
                    "rejected",
                    "withdrawn",
                    "expired",
                    "superseded",
                },
                "claim.status",
            ),
            expires_at=_optional_text(mapping.get("expires_at"), "claim.expires_at"),
            claim_sha256=_optional_sha256(mapping.get("claim_sha256"), "claim.claim_sha256"),
        )

    def hash_payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "claim_type": self.claim_type,
            "maturity": self.maturity,
            "scope": self.scope,
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "validation_refs": [item.to_dict() for item in self.validation_refs],
            "assumption_refs": [item.to_dict() for item in self.assumption_refs],
            "limitations": list(self.limitations),
            "prohibited_interpretations": list(self.prohibited_interpretations),
        }

    def computed_sha256(self) -> str:
        return canonical_hash(self.hash_payload())


@dataclass(frozen=True, slots=True)
class Study:
    study_id: str
    scientific_question: str
    purpose: str
    domain: dict[str, Any]
    model_ref: ArtifactRef
    registry_ref: ArtifactRef
    backend_policy: dict[str, Any]
    object_refs: tuple[ObjectRef, ...]
    lifecycle_state: str
    claim_ceiling: Maturity
    calibration_validation_policy: dict[str, Any]
    owners: tuple[dict[str, Any], ...]
    approvals: tuple[dict[str, Any], ...]
    confidentiality: str
    provenance: dict[str, Any]

    object_type: ClassVar[ResearchObjectType] = "study"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Study:
        mapping = _mapping(data, "study")
        _reject_unknown(
            mapping,
            {
                "study_id",
                "scientific_question",
                "purpose",
                "domain",
                "model_ref",
                "registry_ref",
                "backend_policy",
                "object_refs",
                "lifecycle_state",
                "claim_ceiling",
                "calibration_validation_policy",
                "owners",
                "approvals",
                "confidentiality",
                "provenance",
            },
            "study",
        )
        backend_policy = _json_object(
            mapping.get("backend_policy"), "study.backend_policy"
        )
        allowed_backends = backend_policy.get("allowed_backends")
        if not isinstance(allowed_backends, list) or not allowed_backends:
            raise ResearchValidationError(
                "study.backend_policy.allowed_backends must be a non-empty array"
            )
        normalized_backends = []
        for index, item in enumerate(allowed_backends):
            normalized_backends.append(
                _enum(
                    item,
                    {"mock", "aspen_plus", "hysys"},
                    f"study.backend_policy.allowed_backends[{index}]",
                )
            )
        allow_mock = backend_policy.get("allow_mock")
        require_licensed = backend_policy.get("require_licensed_windows")
        if not isinstance(allow_mock, bool) or not isinstance(require_licensed, bool):
            raise ResearchValidationError(
                "study.backend_policy requires boolean allow_mock and require_licensed_windows"
            )
        if not allow_mock and "mock" in normalized_backends:
            raise ResearchValidationError(
                "study.backend_policy cannot include mock when allow_mock is false"
            )
        if require_licensed and not {"aspen_plus", "hysys"}.intersection(normalized_backends):
            raise ResearchValidationError(
                "licensed study requires aspen_plus or hysys in allowed_backends"
            )
        backend_policy["allowed_backends"] = normalized_backends
        return cls(
            study_id=_id(mapping.get("study_id"), "study", "study.study_id"),
            scientific_question=_text(
                mapping.get("scientific_question"), "study.scientific_question"
            ),
            purpose=_enum(
                mapping.get("purpose"),
                {
                    "source_reproduction",
                    "calibration",
                    "validation",
                    "sensitivity",
                    "design_specification",
                    "optimization",
                    "dynamic_transition",
                    "hybrid_modeling",
                    "uncertainty_quantification",
                },
                "study.purpose",
            ),
            domain=_json_object(mapping.get("domain"), "study.domain"),
            model_ref=ArtifactRef.from_dict(
                _mapping(mapping.get("model_ref"), "study.model_ref"),
                label="study.model_ref",
            ),
            registry_ref=ArtifactRef.from_dict(
                _mapping(mapping.get("registry_ref"), "study.registry_ref"),
                label="study.registry_ref",
            ),
            backend_policy=backend_policy,
            object_refs=_refs(
                mapping.get("object_refs", []), "study.object_refs", nonempty=True
            ),
            lifecycle_state=_enum(
                mapping.get("lifecycle_state"), set(_LIFECYCLE_RANK), "study.lifecycle_state"
            ),
            claim_ceiling=cast(
                Maturity,
                _enum(
                    mapping.get("claim_ceiling"), set(_MATURITY_RANK), "study.claim_ceiling"
                ),
            ),
            calibration_validation_policy=_json_object(
                mapping.get("calibration_validation_policy"),
                "study.calibration_validation_policy",
            ),
            owners=tuple(
                _json_object(item, f"study.owners[{index}]")
                for index, item in enumerate(
                    _sequence(mapping.get("owners", []), "study.owners")
                )
            ),
            approvals=tuple(
                _json_object(item, f"study.approvals[{index}]")
                for index, item in enumerate(
                    _sequence(mapping.get("approvals", []), "study.approvals")
                )
            ),
            confidentiality=_enum(
                mapping.get("confidentiality"),
                {"public", "internal", "restricted", "confidential"},
                "study.confidentiality",
            ),
            provenance=_json_object(mapping.get("provenance"), "study.provenance"),
        )
