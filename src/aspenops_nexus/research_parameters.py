from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from .research_common import (
    ObjectRef,
    ResearchObjectType,
    ResearchValidationError,
    SemanticBinding,
    SourceRef,
    _enum,
    _finite_number,
    _id,
    _json_object,
    _mapping,
    _optional_text,
    _refs,
    _reject_unknown,
    _scalar,
    _sequence,
    _sources,
    _strings,
    _text,
)


@dataclass(frozen=True, slots=True)
class Parameter:
    parameter_id: str
    category: str
    semantic_binding: SemanticBinding
    mechanism: str | None
    site: str | None
    components: tuple[str, ...]
    unit: str
    representation: str
    initial_value: str | int | float | bool
    bounds: dict[str, float] | None
    mode: str
    sharing_scope: str
    temperature_form: dict[str, Any] | None
    source: SourceRef
    ties: tuple[dict[str, Any], ...]
    prior: dict[str, Any] | None
    identifiability: str | dict[str, Any]
    physicality_checks: tuple[dict[str, Any], ...]

    object_type: ClassVar[ResearchObjectType] = "parameter"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Parameter:
        mapping = _mapping(data, "parameter")
        _reject_unknown(
            mapping,
            {
                "parameter_id",
                "category",
                "semantic_binding",
                "mechanism",
                "site",
                "components",
                "unit",
                "representation",
                "initial_value",
                "bounds",
                "mode",
                "sharing_scope",
                "temperature_form",
                "source",
                "ties",
                "prior",
                "identifiability",
                "physicality_checks",
            },
            "parameter",
        )
        semantic_binding = SemanticBinding.from_dict(
            _mapping(mapping.get("semantic_binding"), "parameter.semantic_binding"),
            label="parameter.semantic_binding",
        )
        if semantic_binding.access != "write":
            raise ResearchValidationError("parameter.semantic_binding.access must be write")
        bounds_value = mapping.get("bounds")
        bounds: dict[str, float] | None = None
        if bounds_value is not None:
            bounds_mapping = _mapping(bounds_value, "parameter.bounds")
            _reject_unknown(bounds_mapping, {"lower", "upper"}, "parameter.bounds")
            lower = _finite_number(bounds_mapping.get("lower"), "parameter.bounds.lower")
            upper = _finite_number(bounds_mapping.get("upper"), "parameter.bounds.upper")
            if upper <= lower:
                raise ResearchValidationError("parameter.bounds requires lower < upper")
            bounds = {"lower": lower, "upper": upper}
        mode = _enum(
            mapping.get("mode"),
            {"fixed", "estimated", "derived", "tied", "screened_out"},
            "parameter.mode",
        )
        if mode == "estimated" and bounds is None:
            raise ResearchValidationError("estimated parameter requires finite bounds")
        representation = _enum(
            mapping.get("representation"), {"linear", "log", "log10"}, "parameter.representation"
        )
        initial_value = _scalar(mapping.get("initial_value"), "parameter.initial_value")
        if representation in {"log", "log10"}:
            if isinstance(initial_value, bool | str) or float(initial_value) <= 0:
                raise ResearchValidationError(
                    "log-represented parameter initial_value must be positive"
                )
            if bounds is not None and bounds["lower"] <= 0:
                raise ResearchValidationError(
                    "log-represented parameter lower bound must be positive"
                )
        identifiability_value = mapping.get("identifiability")
        identifiability: str | dict[str, Any]
        if isinstance(identifiability_value, str):
            identifiability = _enum(
                identifiability_value,
                {"unknown", "screened", "weak", "acceptable", "non_identifiable"},
                "parameter.identifiability",
            )
        else:
            identifiability = _json_object(
                identifiability_value, "parameter.identifiability"
            )
        return cls(
            parameter_id=_id(
                mapping.get("parameter_id"), "parameter", "parameter.parameter_id"
            ),
            category=_enum(
                mapping.get("category"),
                {
                    "thermodynamic",
                    "kinetic",
                    "reactor",
                    "correlation",
                    "control",
                    "surrogate",
                    "numerical",
                },
                "parameter.category",
            ),
            semantic_binding=semantic_binding,
            mechanism=_optional_text(mapping.get("mechanism"), "parameter.mechanism"),
            site=_optional_text(mapping.get("site"), "parameter.site"),
            components=_strings(mapping.get("components", []), "parameter.components"),
            unit=_text(mapping.get("unit"), "parameter.unit"),
            representation=representation,
            initial_value=initial_value,
            bounds=bounds,
            mode=mode,
            sharing_scope=_enum(
                mapping.get("sharing_scope"),
                {
                    "global",
                    "catalyst_wide",
                    "site_specific",
                    "grade_specific",
                    "reactor_specific",
                },
                "parameter.sharing_scope",
            ),
            temperature_form=(
                None
                if mapping.get("temperature_form") is None
                else _json_object(mapping["temperature_form"], "parameter.temperature_form")
            ),
            source=SourceRef.from_dict(
                _mapping(mapping.get("source"), "parameter.source"),
                label="parameter.source",
            ),
            ties=tuple(
                _json_object(item, f"parameter.ties[{index}]")
                for index, item in enumerate(
                    _sequence(mapping.get("ties", []), "parameter.ties")
                )
            ),
            prior=(
                None
                if mapping.get("prior") is None
                else _json_object(mapping["prior"], "parameter.prior")
            ),
            identifiability=identifiability,
            physicality_checks=tuple(
                _json_object(item, f"parameter.physicality_checks[{index}]")
                for index, item in enumerate(
                    _sequence(
                        mapping.get("physicality_checks", []),
                        "parameter.physicality_checks",
                    )
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class Assumption:
    assumption_id: str
    statement: str
    category: str
    rationale: str
    evidence_refs: tuple[SourceRef, ...]
    confidence: str
    risk: str | dict[str, Any]
    applicability: dict[str, Any]
    falsification_test: str | dict[str, Any] | None
    status: str
    affected_objects: tuple[ObjectRef, ...]
    claim_restrictions: tuple[str, ...]
    contradiction_group: str | None
    resolution: dict[str, Any] | None

    object_type: ClassVar[ResearchObjectType] = "assumption"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Assumption:
        mapping = _mapping(data, "assumption")
        _reject_unknown(
            mapping,
            {
                "assumption_id",
                "statement",
                "category",
                "rationale",
                "evidence_refs",
                "confidence",
                "risk",
                "applicability",
                "falsification_test",
                "status",
                "affected_objects",
                "claim_restrictions",
                "contradiction_group",
                "resolution",
            },
            "assumption",
        )
        risk_value = mapping.get("risk")
        risk: str | dict[str, Any]
        if isinstance(risk_value, str):
            risk = _enum(risk_value, {"low", "medium", "high", "critical"}, "assumption.risk")
        else:
            risk = _json_object(risk_value, "assumption.risk")
        falsification_value = mapping.get("falsification_test")
        falsification: str | dict[str, Any] | None
        if falsification_value is None:
            falsification = None
        elif isinstance(falsification_value, str):
            falsification = _text(falsification_value, "assumption.falsification_test")
        else:
            falsification = _json_object(
                falsification_value, "assumption.falsification_test"
            )
        return cls(
            assumption_id=_id(
                mapping.get("assumption_id"), "assumption", "assumption.assumption_id"
            ),
            statement=_text(mapping.get("statement"), "assumption.statement"),
            category=_enum(
                mapping.get("category"),
                {
                    "reactor_equivalence",
                    "thermodynamics",
                    "kinetics",
                    "data_substitution",
                    "pseudo_component",
                    "correlation",
                    "numerical",
                    "scope",
                    "source_contradiction",
                },
                "assumption.category",
            ),
            rationale=_text(mapping.get("rationale"), "assumption.rationale"),
            evidence_refs=_sources(
                mapping.get("evidence_refs", []),
                "assumption.evidence_refs",
                nonempty=True,
            ),
            confidence=_enum(
                mapping.get("confidence"),
                {"low", "medium", "high"},
                "assumption.confidence",
            ),
            risk=risk,
            applicability=_json_object(
                mapping.get("applicability"), "assumption.applicability"
            ),
            falsification_test=falsification,
            status=_enum(
                mapping.get("status"),
                {"proposed", "accepted", "challenged", "rejected", "superseded", "unresolved"},
                "assumption.status",
            ),
            affected_objects=_refs(
                mapping.get("affected_objects", []),
                "assumption.affected_objects",
                nonempty=True,
            ),
            claim_restrictions=_strings(
                mapping.get("claim_restrictions", []),
                "assumption.claim_restrictions",
                nonempty=True,
            ),
            contradiction_group=_optional_text(
                mapping.get("contradiction_group"), "assumption.contradiction_group"
            ),
            resolution=(
                None
                if mapping.get("resolution") is None
                else _json_object(mapping["resolution"], "assumption.resolution")
            ),
        )
