from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias, cast

from .hashing import canonical_hash
from .process_requirement import SourceStatus

# Private compatibility alias; implementation lives in hashing.py.
_canonical_hash = canonical_hash

DESIGN_SCHEMA = "aspenops.flowsheet/v2"
MAX_COMPONENTS = 256
MAX_EQUIPMENT = 512
MAX_STREAMS = 2048
MAX_PORTS_PER_EQUIPMENT = 64
MAX_PARAMETERS_PER_EQUIPMENT = 256
MAX_REACTIONS = 512
MAX_RECYCLES = 128
MAX_TEXT_LENGTH = 4096

PortDirection = Literal["in", "out"]
PortDomain = Literal["material", "energy", "information"]
StreamKind = Literal[
    "material",
    "energy",
    "information",
    "tear",
    "feed",
    "product",
    "waste",
    "utility",
]
ReactionKind = Literal[
    "stoichiometric",
    "yield",
    "equilibrium",
    "gibbs",
    "kinetic",
    "polymerization",
    "user_model",
]
ScalarValue: TypeAlias = str | int | float | bool

_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,31}$")
_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
_SOURCE_STATUSES = {
    "USER_PROVIDED",
    "APPROVED_DEFAULT",
    "INFERRED_PENDING_APPROVAL",
    "UNKNOWN",
}
_PORT_DIRECTIONS = {"in", "out"}
_PORT_DOMAINS = {"material", "energy", "information"}
_STREAM_KINDS = {
    "material",
    "energy",
    "information",
    "tear",
    "feed",
    "product",
    "waste",
    "utility",
}
_TARGET_SIMULATORS = {"aspen_plus", "hysys"}
_TARGET_VERSIONS = {"14", "15", "approved-version"}
_REACTION_KINDS = {
    "stoichiometric",
    "yield",
    "equilibrium",
    "gibbs",
    "kinetic",
    "polymerization",
    "user_model",
}
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


def _bounded_object(value: Any, label: str, *, maximum: int) -> dict[str, Any]:
    mapping = _object(value, label)
    if len(mapping) > maximum:
        raise ValueError(f"{label} contains {len(mapping)} entries; limit is {maximum}")
    return mapping


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


def _optional_text(value: Any, label: str) -> str | None:
    return None if value is None else _text(value, label)


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def _positive(value: Any, label: str) -> float:
    number = _finite(value, label)
    if number <= 0:
        raise ValueError(f"{label} must be positive")
    return number


def _scalar(value: Any, label: str) -> ScalarValue:
    if isinstance(value, str):
        return _text(value, label)
    if isinstance(value, bool | int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError(f"{label} must be a finite scalar JSON value")


@dataclass(frozen=True, slots=True)
class ComponentDefinition:
    id: str
    display_name: str
    vendor_ids: dict[str, str]
    cas: str | None = None
    formula: str | None = None
    molecular_weight: float | None = None
    pseudo_component: bool = False
    electrolyte: bool = False
    polymer: bool = False
    solid: bool = False
    status: SourceStatus = "UNKNOWN"

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> ComponentDefinition:
        mapping = _object(value, label)
        allowed = {
            "id",
            "display_name",
            "vendor_ids",
            "cas",
            "formula",
            "molecular_weight",
            "pseudo_component",
            "electrolyte",
            "polymer",
            "solid",
            "status",
        }
        unknown = sorted(set(mapping) - allowed)
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        vendor_mapping = _bounded_object(
            mapping.get("vendor_ids", {}),
            f"{label}.vendor_ids",
            maximum=16,
        )
        vendor_ids = {
            _text(vendor, f"{label}.vendor name").casefold(): _text(
                identifier,
                f"{label}.vendor_ids.{vendor}",
            )
            for vendor, identifier in vendor_mapping.items()
        }
        cas = _optional_text(mapping.get("cas"), f"{label}.cas")
        if cas is not None and _CAS_RE.fullmatch(cas) is None:
            raise ValueError(f"{label}.cas is not a valid CAS number")
        molecular_weight_raw = mapping.get("molecular_weight")
        molecular_weight = (
            None
            if molecular_weight_raw is None
            else _positive(molecular_weight_raw, f"{label}.molecular_weight")
        )

        def boolean(name: str) -> bool:
            item = mapping.get(name, False)
            if not isinstance(item, bool):
                raise ValueError(f"{label}.{name} must be a boolean")
            return item

        return cls(
            id=_identifier(mapping.get("id"), f"{label}.id"),
            display_name=_text(
                mapping.get("display_name", mapping.get("id")), f"{label}.display_name"
            ),
            vendor_ids=vendor_ids,
            cas=cas,
            formula=_optional_text(mapping.get("formula"), f"{label}.formula"),
            molecular_weight=molecular_weight,
            pseudo_component=boolean("pseudo_component"),
            electrolyte=boolean("electrolyte"),
            polymer=boolean("polymer"),
            solid=boolean("solid"),
            status=_status(mapping.get("status", "UNKNOWN"), f"{label}.status"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "vendor_ids": dict(sorted(self.vendor_ids.items())),
            "cas": self.cas,
            "formula": self.formula,
            "molecular_weight": self.molecular_weight,
            "pseudo_component": self.pseudo_component,
            "electrolyte": self.electrolyte,
            "polymer": self.polymer,
            "solid": self.solid,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class PropertyMethodDefinition:
    id: str
    vendor: str
    supported_versions: tuple[str, ...]
    phase_scope: tuple[str, ...]
    rationale: str
    status: SourceStatus

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> PropertyMethodDefinition:
        mapping = _object(value, label)
        allowed = {
            "id",
            "vendor",
            "supported_versions",
            "phase_scope",
            "rationale",
            "status",
        }
        unknown = sorted(set(mapping) - allowed)
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        versions = tuple(
            _text(item, f"{label}.supported_versions[{index}]")
            for index, item in enumerate(
                _array(
                    mapping.get("supported_versions", []),
                    f"{label}.supported_versions",
                    maximum=32,
                )
            )
        )
        phase_scope = tuple(
            _text(item, f"{label}.phase_scope[{index}]").casefold()
            for index, item in enumerate(
                _array(mapping.get("phase_scope", []), f"{label}.phase_scope", maximum=32)
            )
        )
        if len(set(versions)) != len(versions) or len(set(phase_scope)) != len(phase_scope):
            raise ValueError(f"{label} version and phase lists must be unique")
        return cls(
            id=_identifier(mapping.get("id"), f"{label}.id"),
            vendor=_text(mapping.get("vendor"), f"{label}.vendor").casefold(),
            supported_versions=versions,
            phase_scope=phase_scope,
            rationale=_text(mapping.get("rationale"), f"{label}.rationale"),
            status=_status(mapping.get("status", "UNKNOWN"), f"{label}.status"),
        )

    @property
    def approved(self) -> bool:
        return self.status in {"USER_PROVIDED", "APPROVED_DEFAULT"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "vendor": self.vendor,
            "supported_versions": list(self.supported_versions),
            "phase_scope": list(self.phase_scope),
            "rationale": self.rationale,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class PortDefinition:
    id: str
    direction: PortDirection
    domain: PortDomain
    required: bool = True
    multiple: bool = False

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> PortDefinition:
        mapping = _object(value, label)
        unknown = sorted(set(mapping) - {"id", "direction", "domain", "required", "multiple"})
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        direction = _text(mapping.get("direction"), f"{label}.direction").casefold()
        if direction not in _PORT_DIRECTIONS:
            raise ValueError(f"{label}.direction must be in or out")
        domain = _text(mapping.get("domain"), f"{label}.domain").casefold()
        if domain not in _PORT_DOMAINS:
            raise ValueError(f"{label}.domain must be material, energy or information")
        required = mapping.get("required", True)
        multiple = mapping.get("multiple", False)
        if not isinstance(required, bool) or not isinstance(multiple, bool):
            raise ValueError(f"{label}.required and multiple must be booleans")
        return cls(
            id=_identifier(mapping.get("id"), f"{label}.id"),
            direction=cast(PortDirection, direction),
            domain=cast(PortDomain, domain),
            required=required,
            multiple=multiple,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "direction": self.direction,
            "domain": self.domain,
            "required": self.required,
            "multiple": self.multiple,
        }


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    name: str
    value: ScalarValue | None
    unit: str | None
    status: SourceStatus

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> ParameterDefinition:
        mapping = _object(value, label)
        unknown = sorted(set(mapping) - {"name", "value", "unit", "status"})
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        raw = mapping.get("value")
        normalized = None if raw is None else _scalar(raw, f"{label}.value")
        status = _status(mapping.get("status", "UNKNOWN"), f"{label}.status")
        if status in {"USER_PROVIDED", "APPROVED_DEFAULT"} and normalized is None:
            raise ValueError(f"{label} cannot be approved without a value")
        return cls(
            name=_identifier(mapping.get("name"), f"{label}.name"),
            value=normalized,
            unit=_optional_text(mapping.get("unit"), f"{label}.unit"),
            status=status,
        )

    @property
    def approved(self) -> bool:
        return self.value is not None and self.status in {"USER_PROVIDED", "APPROVED_DEFAULT"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class EquipmentDefinition:
    id: str
    display_name: str
    kind: str
    vendor_type: str | None
    ports: tuple[PortDefinition, ...]
    parameters: tuple[ParameterDefinition, ...] = ()
    design_specs: tuple[ParameterDefinition, ...] = ()
    contract_version: str = "1"

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> EquipmentDefinition:
        mapping = _object(value, label)
        allowed = {
            "id",
            "display_name",
            "kind",
            "vendor_type",
            "ports",
            "parameters",
            "design_specs",
            "contract_version",
        }
        unknown = sorted(set(mapping) - allowed)
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        ports = tuple(
            PortDefinition.from_dict(item, label=f"{label}.ports[{index}]")
            for index, item in enumerate(
                _array(mapping.get("ports", []), f"{label}.ports", maximum=MAX_PORTS_PER_EQUIPMENT)
            )
        )
        parameters = tuple(
            ParameterDefinition.from_dict(item, label=f"{label}.parameters[{index}]")
            for index, item in enumerate(
                _array(
                    mapping.get("parameters", []),
                    f"{label}.parameters",
                    maximum=MAX_PARAMETERS_PER_EQUIPMENT,
                )
            )
        )
        design_specs = tuple(
            ParameterDefinition.from_dict(item, label=f"{label}.design_specs[{index}]")
            for index, item in enumerate(
                _array(
                    mapping.get("design_specs", []),
                    f"{label}.design_specs",
                    maximum=MAX_PARAMETERS_PER_EQUIPMENT,
                )
            )
        )
        for item_label, identifiers in (
            ("ports", [item.id for item in ports]),
            ("parameters", [item.name for item in parameters]),
            ("design_specs", [item.name for item in design_specs]),
        ):
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f"{label}.{item_label} must contain unique IDs")
        return cls(
            id=_identifier(mapping.get("id"), f"{label}.id"),
            display_name=_text(
                mapping.get("display_name", mapping.get("id")), f"{label}.display_name"
            ),
            kind=_text(mapping.get("kind"), f"{label}.kind").casefold(),
            vendor_type=_optional_text(mapping.get("vendor_type"), f"{label}.vendor_type"),
            ports=ports,
            parameters=parameters,
            design_specs=design_specs,
            contract_version=_text(
                mapping.get("contract_version", "1"),
                f"{label}.contract_version",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "kind": self.kind,
            "vendor_type": self.vendor_type,
            "ports": [item.to_dict() for item in self.ports],
            "parameters": [item.to_dict() for item in self.parameters],
            "design_specs": [item.to_dict() for item in self.design_specs],
            "contract_version": self.contract_version,
        }


@dataclass(frozen=True, slots=True)
class Endpoint:
    equipment_id: str
    port_id: str

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> Endpoint:
        mapping = _object(value, label)
        unknown = sorted(set(mapping) - {"equipment_id", "port_id"})
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        return cls(
            equipment_id=_identifier(mapping.get("equipment_id"), f"{label}.equipment_id"),
            port_id=_identifier(mapping.get("port_id"), f"{label}.port_id"),
        )

    def to_dict(self) -> dict[str, str]:
        return {"equipment_id": self.equipment_id, "port_id": self.port_id}


@dataclass(frozen=True, slots=True)
class StreamDefinition:
    id: str
    display_name: str
    kind: StreamKind
    source: Endpoint
    target: Endpoint
    components: tuple[str, ...] = ()
    parameters: tuple[ParameterDefinition, ...] = ()

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> StreamDefinition:
        mapping = _object(value, label)
        allowed = {"id", "display_name", "kind", "source", "target", "components", "parameters"}
        unknown = sorted(set(mapping) - allowed)
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        kind = _text(mapping.get("kind", "material"), f"{label}.kind").casefold()
        if kind not in _STREAM_KINDS:
            raise ValueError(f"{label}.kind is unsupported: {kind}")
        components = tuple(
            _identifier(item, f"{label}.components[{index}]")
            for index, item in enumerate(
                _array(mapping.get("components", []), f"{label}.components", maximum=MAX_COMPONENTS)
            )
        )
        if len(set(components)) != len(components):
            raise ValueError(f"{label}.components must contain unique IDs")
        parameters = tuple(
            ParameterDefinition.from_dict(item, label=f"{label}.parameters[{index}]")
            for index, item in enumerate(
                _array(
                    mapping.get("parameters", []),
                    f"{label}.parameters",
                    maximum=MAX_PARAMETERS_PER_EQUIPMENT,
                )
            )
        )
        if len({item.name for item in parameters}) != len(parameters):
            raise ValueError(f"{label}.parameters must contain unique names")
        return cls(
            id=_identifier(mapping.get("id"), f"{label}.id"),
            display_name=_text(
                mapping.get("display_name", mapping.get("id")), f"{label}.display_name"
            ),
            kind=cast(StreamKind, kind),
            source=Endpoint.from_dict(mapping.get("source"), label=f"{label}.source"),
            target=Endpoint.from_dict(mapping.get("target"), label=f"{label}.target"),
            components=components,
            parameters=parameters,
        )

    @property
    def domain(self) -> PortDomain:
        if self.kind in {"energy", "utility"}:
            return "energy"
        if self.kind == "information":
            return "information"
        return "material"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "kind": self.kind,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "components": list(self.components),
            "parameters": [item.to_dict() for item in self.parameters],
        }


@dataclass(frozen=True, slots=True)
class ReactionDefinition:
    id: str
    kind: ReactionKind
    stoichiometry: dict[str, float]
    phase: str
    status: SourceStatus
    parameters: tuple[ParameterDefinition, ...] = ()

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> ReactionDefinition:
        mapping = _object(value, label)
        allowed = {"id", "kind", "stoichiometry", "phase", "status", "parameters"}
        unknown = sorted(set(mapping) - allowed)
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        kind = _text(mapping.get("kind"), f"{label}.kind").casefold()
        if kind not in _REACTION_KINDS:
            raise ValueError(f"{label}.kind is unsupported: {kind}")
        raw_stoichiometry = _bounded_object(
            mapping.get("stoichiometry", {}),
            f"{label}.stoichiometry",
            maximum=MAX_COMPONENTS,
        )
        stoichiometry = {
            _identifier(component, f"{label}.stoichiometry component"): _finite(
                coefficient,
                f"{label}.stoichiometry.{component}",
            )
            for component, coefficient in raw_stoichiometry.items()
        }
        if kind in {"stoichiometric", "kinetic", "equilibrium"} and not stoichiometry:
            raise ValueError(f"{label}.stoichiometry is required for reaction kind {kind}")
        parameters = tuple(
            ParameterDefinition.from_dict(item, label=f"{label}.parameters[{index}]")
            for index, item in enumerate(
                _array(
                    mapping.get("parameters", []),
                    f"{label}.parameters",
                    maximum=MAX_PARAMETERS_PER_EQUIPMENT,
                )
            )
        )
        return cls(
            id=_identifier(mapping.get("id"), f"{label}.id"),
            kind=cast(ReactionKind, kind),
            stoichiometry=stoichiometry,
            phase=_text(mapping.get("phase", "mixed"), f"{label}.phase").casefold(),
            status=_status(mapping.get("status", "UNKNOWN"), f"{label}.status"),
            parameters=parameters,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "stoichiometry": dict(sorted(self.stoichiometry.items())),
            "phase": self.phase,
            "status": self.status,
            "parameters": [item.to_dict() for item in self.parameters],
        }


@dataclass(frozen=True, slots=True)
class RecycleDefinition:
    id: str
    stream_id: str
    tear_stream_id: str
    convergence_variables: tuple[str, ...]
    tolerance: float
    max_iterations: int
    acceleration: str
    status: SourceStatus

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> RecycleDefinition:
        mapping = _object(value, label)
        allowed = {
            "id",
            "stream_id",
            "tear_stream_id",
            "convergence_variables",
            "tolerance",
            "max_iterations",
            "acceleration",
            "status",
        }
        unknown = sorted(set(mapping) - allowed)
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        variables = tuple(
            _identifier(item, f"{label}.convergence_variables[{index}]")
            for index, item in enumerate(
                _array(
                    mapping.get("convergence_variables", []),
                    f"{label}.convergence_variables",
                    maximum=64,
                )
            )
        )
        if not variables or len(set(variables)) != len(variables):
            raise ValueError(f"{label}.convergence_variables must be non-empty and unique")
        max_iterations = mapping.get("max_iterations", 100)
        if isinstance(max_iterations, bool) or not isinstance(max_iterations, int):
            raise ValueError(f"{label}.max_iterations must be an integer")
        if max_iterations < 1 or max_iterations > 100_000:
            raise ValueError(f"{label}.max_iterations is outside the supported range")
        return cls(
            id=_identifier(mapping.get("id"), f"{label}.id"),
            stream_id=_identifier(mapping.get("stream_id"), f"{label}.stream_id"),
            tear_stream_id=_identifier(mapping.get("tear_stream_id"), f"{label}.tear_stream_id"),
            convergence_variables=variables,
            tolerance=_positive(mapping.get("tolerance", 1e-6), f"{label}.tolerance"),
            max_iterations=max_iterations,
            acceleration=_text(
                mapping.get("acceleration", "wegstein"), f"{label}.acceleration"
            ).casefold(),
            status=_status(mapping.get("status", "UNKNOWN"), f"{label}.status"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "stream_id": self.stream_id,
            "tear_stream_id": self.tear_stream_id,
            "convergence_variables": list(self.convergence_variables),
            "tolerance": self.tolerance,
            "max_iterations": self.max_iterations,
            "acceleration": self.acceleration,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class ProcessDesignIR:
    name: str
    target_simulator: str
    target_version: str
    requirement_hash: str
    components: tuple[ComponentDefinition, ...]
    property_method: PropertyMethodDefinition
    equipment: tuple[EquipmentDefinition, ...]
    streams: tuple[StreamDefinition, ...]
    reactions: tuple[ReactionDefinition, ...] = ()
    recycles: tuple[RecycleDefinition, ...] = ()
    schema: str = DESIGN_SCHEMA
    metadata: dict[str, ScalarValue] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Any) -> ProcessDesignIR:
        mapping = _object(value, "process design")
        allowed = {
            "schema",
            "name",
            "target_simulator",
            "target_version",
            "requirement_hash",
            "components",
            "property_method",
            "equipment",
            "streams",
            "reactions",
            "recycles",
            "metadata",
        }
        unknown = sorted(set(mapping) - allowed)
        if unknown:
            raise ValueError(f"process design contains unsupported fields: {', '.join(unknown)}")
        schema = _text(mapping.get("schema", DESIGN_SCHEMA), "process design.schema")
        if schema != DESIGN_SCHEMA:
            raise ValueError(f"Unsupported process design schema: {schema}")
        requirement_hash = _text(mapping.get("requirement_hash"), "process design.requirement_hash")
        if re.fullmatch(r"[0-9a-f]{64}", requirement_hash) is None:
            raise ValueError("process design.requirement_hash must be a SHA-256 digest")
        components = tuple(
            ComponentDefinition.from_dict(item, label=f"process design.components[{index}]")
            for index, item in enumerate(
                _array(
                    mapping.get("components", []),
                    "process design.components",
                    maximum=MAX_COMPONENTS,
                )
            )
        )
        equipment = tuple(
            EquipmentDefinition.from_dict(item, label=f"process design.equipment[{index}]")
            for index, item in enumerate(
                _array(
                    mapping.get("equipment", []), "process design.equipment", maximum=MAX_EQUIPMENT
                )
            )
        )
        streams = tuple(
            StreamDefinition.from_dict(item, label=f"process design.streams[{index}]")
            for index, item in enumerate(
                _array(mapping.get("streams", []), "process design.streams", maximum=MAX_STREAMS)
            )
        )
        reactions = tuple(
            ReactionDefinition.from_dict(item, label=f"process design.reactions[{index}]")
            for index, item in enumerate(
                _array(
                    mapping.get("reactions", []), "process design.reactions", maximum=MAX_REACTIONS
                )
            )
        )
        recycles = tuple(
            RecycleDefinition.from_dict(item, label=f"process design.recycles[{index}]")
            for index, item in enumerate(
                _array(mapping.get("recycles", []), "process design.recycles", maximum=MAX_RECYCLES)
            )
        )
        for label, identifiers in (
            ("components", [item.id for item in components]),
            ("equipment", [item.id for item in equipment]),
            ("streams", [item.id for item in streams]),
            ("reactions", [item.id for item in reactions]),
            ("recycles", [item.id for item in recycles]),
        ):
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f"process design {label} must contain unique IDs")
        metadata_mapping = _bounded_object(
            mapping.get("metadata", {}),
            "process design.metadata",
            maximum=1024,
        )
        metadata = {
            _text(key, "metadata key"): _scalar(item, f"metadata.{key}")
            for key, item in metadata_mapping.items()
        }
        target_simulator = _text(
            mapping.get("target_simulator"),
            "process design.target_simulator",
        ).casefold()
        if target_simulator not in _TARGET_SIMULATORS:
            raise ValueError(f"Unsupported process design simulator: {target_simulator}")
        target_version = _text(
            mapping.get("target_version"),
            "process design.target_version",
        ).casefold()
        if target_version not in _TARGET_VERSIONS:
            raise ValueError(f"Unsupported process design version: {target_version}")
        return cls(
            name=_text(mapping.get("name"), "process design.name"),
            target_simulator=target_simulator,
            target_version=target_version,
            requirement_hash=requirement_hash,
            components=components,
            property_method=PropertyMethodDefinition.from_dict(
                mapping.get("property_method"),
                label="process design.property_method",
            ),
            equipment=equipment,
            streams=streams,
            reactions=reactions,
            recycles=recycles,
            schema=schema,
            metadata=metadata,
        )

    def normalized(self) -> ProcessDesignIR:
        return ProcessDesignIR(
            name=self.name,
            target_simulator=self.target_simulator,
            target_version=self.target_version,
            requirement_hash=self.requirement_hash,
            components=tuple(sorted(self.components, key=lambda item: item.id)),
            property_method=self.property_method,
            equipment=tuple(sorted(self.equipment, key=lambda item: item.id)),
            streams=tuple(sorted(self.streams, key=lambda item: item.id)),
            reactions=tuple(sorted(self.reactions, key=lambda item: item.id)),
            recycles=tuple(sorted(self.recycles, key=lambda item: item.id)),
            schema=self.schema,
            metadata=dict(sorted(self.metadata.items())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "target_simulator": self.target_simulator,
            "target_version": self.target_version,
            "requirement_hash": self.requirement_hash,
            "components": [item.to_dict() for item in self.components],
            "property_method": self.property_method.to_dict(),
            "equipment": [item.to_dict() for item in self.equipment],
            "streams": [item.to_dict() for item in self.streams],
            "reactions": [item.to_dict() for item in self.reactions],
            "recycles": [item.to_dict() for item in self.recycles],
            "metadata": dict(self.metadata),
        }

    def canonical_dict(self) -> dict[str, Any]:
        return self.normalized().to_dict()

    def digest(self) -> str:
        return canonical_hash(self.canonical_dict())
