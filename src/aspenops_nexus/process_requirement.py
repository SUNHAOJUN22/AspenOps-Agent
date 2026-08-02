from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias, cast

REQUIREMENT_SCHEMA = "aspenops.process-requirement/v1"
MAX_FEEDS = 128
MAX_PRODUCTS = 128
MAX_COMPONENTS_PER_FEED = 256
MAX_TEXT_LENGTH = 4096

SourceStatus = Literal[
    "USER_PROVIDED",
    "APPROVED_DEFAULT",
    "INFERRED_PENDING_APPROVAL",
    "UNKNOWN",
]
ReadinessStatus = Literal["READY_FOR_DESIGN", "NEEDS_ENGINEERING_INPUT"]
SimulatorName = Literal["aspen_plus", "hysys"]
CompositionBasis = Literal["mole", "mass"]
ScalarValue: TypeAlias = str | int | float | bool

_SOURCE_STATUSES = {
    "USER_PROVIDED",
    "APPROVED_DEFAULT",
    "INFERRED_PENDING_APPROVAL",
    "UNKNOWN",
}
_SIMULATORS = {"aspen_plus", "hysys"}
_TARGET_VERSIONS = {"auto", "14", "15", "approved-version"}
_PHASES = {"vapor", "liquid", "vapor-liquid", "solid", "mixed", "unknown"}
_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")
_BIDI_CONTROLS = {
    "\u061c",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _array(value: Any, label: str, *, maximum: int) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    if len(value) > maximum:
        raise ValueError(f"{label} contains {len(value)} items; limit is {maximum}")
    return value


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    normalized = unicodedata.normalize("NFC", value.strip())
    if not allow_empty and not normalized:
        raise ValueError(f"{label} must be a non-empty string")
    if len(normalized) > MAX_TEXT_LENGTH:
        raise ValueError(f"{label} exceeds {MAX_TEXT_LENGTH} characters")
    if "\x00" in normalized or "\ufffd" in normalized:
        raise ValueError(f"{label} contains an unsafe Unicode character")
    if any(character in _BIDI_CONTROLS for character in normalized):
        raise ValueError(f"{label} contains a bidirectional-control character")
    if any(unicodedata.category(character) == "Cc" for character in normalized):
        raise ValueError(f"{label} contains a control character")
    return normalized


def _identifier(value: Any, label: str) -> str:
    identifier = _text(value, label)
    if _ID_RE.fullmatch(identifier) is None:
        raise ValueError(f"{label} must match {_ID_RE.pattern}")
    return identifier


def _status(value: Any, label: str) -> SourceStatus:
    normalized = _text(value, label)
    if normalized not in _SOURCE_STATUSES:
        raise ValueError(f"{label} must be one of {sorted(_SOURCE_STATUSES)}")
    return cast(SourceStatus, normalized)


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def _safe_scalar(value: Any, label: str) -> ScalarValue:
    if isinstance(value, bool | str | int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError(f"{label} must be a finite scalar JSON value")


def _optional_text(value: Any, label: str) -> str | None:
    return None if value is None else _text(value, label)


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class QualifiedScalar:
    value: ScalarValue | None
    status: SourceStatus
    unit: str | None = None
    uncertainty: float | None = None

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> QualifiedScalar:
        mapping = _object(value, label)
        unknown = sorted(set(mapping) - {"value", "status", "unit", "uncertainty"})
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        raw_value = mapping.get("value")
        scalar = None if raw_value is None else _safe_scalar(raw_value, f"{label}.value")
        uncertainty_raw = mapping.get("uncertainty")
        uncertainty = (
            None if uncertainty_raw is None else _finite(uncertainty_raw, f"{label}.uncertainty")
        )
        if uncertainty is not None and uncertainty < 0:
            raise ValueError(f"{label}.uncertainty must be non-negative")
        status = _status(mapping.get("status", "UNKNOWN"), f"{label}.status")
        if status in {"USER_PROVIDED", "APPROVED_DEFAULT"} and scalar is None:
            raise ValueError(f"{label} cannot be {status} without a value")
        return cls(
            value=scalar,
            status=status,
            unit=_optional_text(mapping.get("unit"), f"{label}.unit"),
            uncertainty=uncertainty,
        )

    @property
    def approved(self) -> bool:
        return self.status in {"USER_PROVIDED", "APPROVED_DEFAULT"} and self.value is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "status": self.status,
            "unit": self.unit,
            "uncertainty": self.uncertainty,
        }


@dataclass(frozen=True, slots=True)
class CompositionEntry:
    component_id: str
    fraction: float
    basis: CompositionBasis
    status: SourceStatus

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> CompositionEntry:
        mapping = _object(value, label)
        unknown = sorted(set(mapping) - {"component_id", "fraction", "basis", "status"})
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        basis = _text(mapping.get("basis", "mole"), f"{label}.basis")
        if basis not in {"mole", "mass"}:
            raise ValueError(f"{label}.basis must be mole or mass")
        fraction = _finite(mapping.get("fraction"), f"{label}.fraction")
        if not 0.0 <= fraction <= 1.0:
            raise ValueError(f"{label}.fraction must be between zero and one")
        return cls(
            component_id=_identifier(mapping.get("component_id"), f"{label}.component_id"),
            fraction=fraction,
            basis=cast(CompositionBasis, basis),
            status=_status(mapping.get("status", "UNKNOWN"), f"{label}.status"),
        )

    @property
    def approved(self) -> bool:
        return self.status in {"USER_PROVIDED", "APPROVED_DEFAULT"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "fraction": self.fraction,
            "basis": self.basis,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class FeedRequirement:
    id: str
    display_name: str
    components: tuple[str, ...]
    composition: tuple[CompositionEntry, ...]
    total_flow: QualifiedScalar
    temperature: QualifiedScalar
    pressure: QualifiedScalar
    phase: str

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> FeedRequirement:
        mapping = _object(value, label)
        allowed = {
            "id",
            "display_name",
            "components",
            "composition",
            "total_flow",
            "temperature",
            "pressure",
            "phase",
        }
        unknown = sorted(set(mapping) - allowed)
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        component_items = _array(
            mapping.get("components", []),
            f"{label}.components",
            maximum=MAX_COMPONENTS_PER_FEED,
        )
        components = tuple(
            _identifier(item, f"{label}.components[{index}]")
            for index, item in enumerate(component_items)
        )
        if len(set(components)) != len(components):
            raise ValueError(f"{label}.components must contain unique IDs")
        composition_items = _array(
            mapping.get("composition", []),
            f"{label}.composition",
            maximum=MAX_COMPONENTS_PER_FEED,
        )
        composition = tuple(
            CompositionEntry.from_dict(item, label=f"{label}.composition[{index}]")
            for index, item in enumerate(composition_items)
        )
        composition_ids = [item.component_id for item in composition]
        if len(set(composition_ids)) != len(composition_ids):
            raise ValueError(f"{label}.composition repeats a component")
        unknown_components = sorted(set(composition_ids) - set(components))
        if unknown_components:
            raise ValueError(
                f"{label}.composition references undeclared components: "
                + ", ".join(unknown_components)
            )
        bases = {item.basis for item in composition}
        if len(bases) > 1:
            raise ValueError(f"{label}.composition cannot mix mole and mass basis")
        if composition:
            total = math.fsum(item.fraction for item in composition)
            if abs(total - 1.0) > 1e-9:
                raise ValueError(f"{label}.composition fractions must sum to one")
        phase = _text(mapping.get("phase", "unknown"), f"{label}.phase").casefold()
        if phase not in _PHASES:
            raise ValueError(f"{label}.phase is unsupported: {phase}")
        return cls(
            id=_identifier(mapping.get("id"), f"{label}.id"),
            display_name=_text(
                mapping.get("display_name", mapping.get("id")), f"{label}.display_name"
            ),
            components=components,
            composition=composition,
            total_flow=QualifiedScalar.from_dict(
                mapping.get("total_flow", {"value": None, "status": "UNKNOWN"}),
                label=f"{label}.total_flow",
            ),
            temperature=QualifiedScalar.from_dict(
                mapping.get("temperature", {"value": None, "status": "UNKNOWN"}),
                label=f"{label}.temperature",
            ),
            pressure=QualifiedScalar.from_dict(
                mapping.get("pressure", {"value": None, "status": "UNKNOWN"}),
                label=f"{label}.pressure",
            ),
            phase=phase,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "components": list(self.components),
            "composition": [item.to_dict() for item in self.composition],
            "total_flow": self.total_flow.to_dict(),
            "temperature": self.temperature.to_dict(),
            "pressure": self.pressure.to_dict(),
            "phase": self.phase,
        }


@dataclass(frozen=True, slots=True)
class ProductRequirement:
    id: str
    display_name: str
    specifications: dict[str, QualifiedScalar]

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> ProductRequirement:
        mapping = _object(value, label)
        unknown = sorted(set(mapping) - {"id", "display_name", "specifications"})
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        specification_mapping = _object(
            mapping.get("specifications", {}), f"{label}.specifications"
        )
        specifications: dict[str, QualifiedScalar] = {}
        for raw_name, raw_value in specification_mapping.items():
            name = _text(raw_name, f"{label}.specification name")
            specifications[name] = QualifiedScalar.from_dict(
                raw_value,
                label=f"{label}.specifications.{name}",
            )
        return cls(
            id=_identifier(mapping.get("id"), f"{label}.id"),
            display_name=_text(
                mapping.get("display_name", mapping.get("id")), f"{label}.display_name"
            ),
            specifications=specifications,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "specifications": {
                name: value.to_dict() for name, value in sorted(self.specifications.items())
            },
        }


@dataclass(frozen=True, slots=True)
class RequirementReadiness:
    status: ReadinessStatus
    blockers: tuple[str, ...]
    pending_assumptions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "blockers": list(self.blockers),
            "pending_assumptions": list(self.pending_assumptions),
        }


@dataclass(frozen=True, slots=True)
class ProcessRequirementDocument:
    name: str
    target_simulator: SimulatorName
    target_version: str
    language: str
    objective: str
    feeds: tuple[FeedRequirement, ...]
    products: tuple[ProductRequirement, ...]
    required_sections: tuple[str, ...]
    property_method: QualifiedScalar
    accepted_assumptions: tuple[str, ...] = ()
    unresolved_assumptions: tuple[str, ...] = ()
    requested_outputs: tuple[str, ...] = ()
    schema: str = REQUIREMENT_SCHEMA
    metadata: dict[str, ScalarValue] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Any) -> ProcessRequirementDocument:
        mapping = _object(value, "process requirement")
        allowed = {
            "schema",
            "project",
            "process_objective",
            "feeds",
            "products",
            "required_sections",
            "property_method",
            "assumptions",
            "requested_outputs",
            "metadata",
        }
        unknown = sorted(set(mapping) - allowed)
        if unknown:
            raise ValueError(
                "process requirement contains unsupported fields: " + ", ".join(unknown)
            )
        schema = _text(mapping.get("schema", REQUIREMENT_SCHEMA), "process requirement.schema")
        if schema != REQUIREMENT_SCHEMA:
            raise ValueError(f"Unsupported process requirement schema: {schema}")
        project = _object(mapping.get("project"), "process requirement.project")
        simulator = _text(
            project.get("target_simulator"),
            "process requirement.project.target_simulator",
        ).casefold()
        if simulator not in _SIMULATORS:
            raise ValueError(f"Unsupported target simulator: {simulator}")
        version = _text(
            project.get("target_version", "auto"),
            "process requirement.project.target_version",
        ).casefold()
        if version not in _TARGET_VERSIONS:
            raise ValueError(f"Unsupported target version: {version}")
        objective_mapping = _object(
            mapping.get("process_objective"),
            "process requirement.process_objective",
        )
        feed_items = _array(
            mapping.get("feeds", []),
            "process requirement.feeds",
            maximum=MAX_FEEDS,
        )
        product_items = _array(
            mapping.get("products", []),
            "process requirement.products",
            maximum=MAX_PRODUCTS,
        )
        feeds = tuple(
            FeedRequirement.from_dict(item, label=f"process requirement.feeds[{index}]")
            for index, item in enumerate(feed_items)
        )
        products = tuple(
            ProductRequirement.from_dict(item, label=f"process requirement.products[{index}]")
            for index, item in enumerate(product_items)
        )
        for label, identifiers in (
            ("feeds", [item.id for item in feeds]),
            ("products", [item.id for item in products]),
        ):
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f"process requirement {label} must contain unique IDs")
        assumptions = _object(mapping.get("assumptions", {}), "process requirement.assumptions")
        accepted = tuple(
            _text(item, f"accepted assumption[{index}]")
            for index, item in enumerate(
                _array(assumptions.get("accepted", []), "accepted assumptions", maximum=1024)
            )
        )
        unresolved = tuple(
            _text(item, f"unresolved assumption[{index}]")
            for index, item in enumerate(
                _array(assumptions.get("unresolved", []), "unresolved assumptions", maximum=1024)
            )
        )
        requested_outputs = tuple(
            _text(item, f"requested output[{index}]")
            for index, item in enumerate(
                _array(mapping.get("requested_outputs", []), "requested outputs", maximum=1024)
            )
        )
        sections = tuple(
            _text(item, f"required section[{index}]").casefold()
            for index, item in enumerate(
                _array(mapping.get("required_sections", []), "required sections", maximum=128)
            )
        )
        if len(set(sections)) != len(sections):
            raise ValueError("required_sections must contain unique values")
        metadata_mapping = _object(mapping.get("metadata", {}), "process requirement.metadata")
        metadata = {
            _text(key, "metadata key"): _safe_scalar(item, f"metadata.{key}")
            for key, item in metadata_mapping.items()
        }
        return cls(
            name=_text(project.get("name"), "process requirement.project.name"),
            target_simulator=cast(SimulatorName, simulator),
            target_version=version,
            language=_text(project.get("language", "en"), "process requirement.project.language"),
            objective=_text(
                objective_mapping.get("description"),
                "process requirement.process_objective.description",
            ),
            feeds=feeds,
            products=products,
            required_sections=sections,
            property_method=QualifiedScalar.from_dict(
                mapping.get("property_method", {"value": None, "status": "UNKNOWN"}),
                label="process requirement.property_method",
            ),
            accepted_assumptions=accepted,
            unresolved_assumptions=unresolved,
            requested_outputs=requested_outputs,
            schema=schema,
            metadata=metadata,
        )

    def readiness(self) -> RequirementReadiness:
        blockers: list[str] = []
        pending: list[str] = list(self.unresolved_assumptions)
        if not self.feeds:
            blockers.append("At least one feed is required")
        if not self.products:
            blockers.append("At least one product is required")
        if not self.property_method.approved:
            blockers.append("Property method requires explicit engineering approval")
        for feed in self.feeds:
            if not feed.components:
                blockers.append(f"Feed {feed.id} has no declared components")
            if not feed.composition or not all(item.approved for item in feed.composition):
                blockers.append(f"Feed {feed.id} composition is incomplete or unapproved")
            for name, value in (
                ("total flow", feed.total_flow),
                ("temperature", feed.temperature),
                ("pressure", feed.pressure),
            ):
                if not value.approved:
                    blockers.append(f"Feed {feed.id} {name} is incomplete or unapproved")
        for product in self.products:
            if not product.specifications:
                blockers.append(f"Product {product.id} has no required specification")
            for name, value in product.specifications.items():
                if not value.approved:
                    blockers.append(
                        f"Product {product.id} specification {name} is incomplete or unapproved"
                    )
        if pending:
            blockers.append("One or more engineering assumptions remain unresolved")
        ordered_blockers = tuple(dict.fromkeys(blockers))
        status: ReadinessStatus = (
            "READY_FOR_DESIGN" if not ordered_blockers else "NEEDS_ENGINEERING_INPUT"
        )
        return RequirementReadiness(status, ordered_blockers, tuple(pending))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "project": {
                "name": self.name,
                "target_simulator": self.target_simulator,
                "target_version": self.target_version,
                "language": self.language,
            },
            "process_objective": {"description": self.objective},
            "feeds": [item.to_dict() for item in self.feeds],
            "products": [item.to_dict() for item in self.products],
            "required_sections": list(self.required_sections),
            "property_method": self.property_method.to_dict(),
            "assumptions": {
                "accepted": list(self.accepted_assumptions),
                "unresolved": list(self.unresolved_assumptions),
            },
            "requested_outputs": list(self.requested_outputs),
            "metadata": dict(self.metadata),
        }

    def digest(self) -> str:
        return _canonical_hash(self.to_dict())
