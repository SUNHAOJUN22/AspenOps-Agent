from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal, cast

IR_SCHEMA = "aspenops.flowsheet/v1"
MAX_COMPONENTS = 256
MAX_UNITS = 512
MAX_STREAMS = 2048
MAX_PORTS_PER_UNIT = 64
MAX_PARAMETERS_PER_ENTITY = 256
MAX_METADATA_BYTES = 262_144
MAX_JSON_DEPTH = 8

Identifier = str
ScalarValue = str | int | float | bool
PortDirection = Literal["in", "out"]
IssueSeverity = Literal["error", "warning"]

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_FORBIDDEN_METADATA_KEYS = {
    "aspen_tree_path",
    "code",
    "command",
    "python",
    "script",
    "shell",
    "tree_path",
    "vba",
}
_CANONICAL_UNIT_KINDS = frozenset(
    {
        "compressor",
        "controller",
        "cooler",
        "custom",
        "distillation_column",
        "feed",
        "flash",
        "heat_exchanger",
        "heater",
        "mixer",
        "product",
        "pump",
        "reactor_cstr",
        "reactor_equilibrium",
        "reactor_pfr",
        "recycle",
        "separator",
        "splitter",
        "valve",
    }
)


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _text(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    normalized = value.strip()
    if nonempty and not normalized:
        raise ValueError(f"{label} must be a non-empty string")
    return normalized


def _optional_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _identifier(value: Any, label: str) -> Identifier:
    identifier = _text(value, label)
    if not _IDENTIFIER.fullmatch(identifier):
        raise ValueError(
            f"{label} must match {_IDENTIFIER.pattern} and contain at most 64 characters"
        )
    return identifier


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _scalar(value: Any, label: str) -> ScalarValue:
    if isinstance(value, bool | str | int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError(f"{label} must be a finite scalar JSON value")


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")


def _safe_json(value: Any, label: str, *, depth: int = 0) -> Any:
    if depth > MAX_JSON_DEPTH:
        raise ValueError(f"{label} exceeds maximum JSON nesting depth {MAX_JSON_DEPTH}")
    if value is None or isinstance(value, bool | str | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} contains a non-finite number")
        return value
    if isinstance(value, list):
        return [
            _safe_json(item, f"{label}[{index}]", depth=depth + 1)
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = _text(raw_key, f"{label} key")
            if key.casefold() in _FORBIDDEN_METADATA_KEYS:
                raise ValueError(f"{label} key is forbidden in simulator-neutral IR: {key}")
            result[key] = _safe_json(item, f"{label}.{key}", depth=depth + 1)
        return result
    raise ValueError(f"{label} contains a non-JSON value")


def _metadata(value: Any, label: str) -> dict[str, Any]:
    metadata = cast(dict[str, Any], _safe_json(_object(value, label), label))
    encoded = json.dumps(
        metadata,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > MAX_METADATA_BYTES:
        raise ValueError(f"{label} exceeds {MAX_METADATA_BYTES} bytes")
    return metadata


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    name: Identifier
    value: ScalarValue
    unit: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str = "parameter") -> ParameterSpec:
        mapping = _object(data, label)
        _reject_unknown(mapping, {"name", "value", "unit"}, label)
        if "name" not in mapping or "value" not in mapping:
            raise ValueError(f"{label} requires name and value")
        name = _identifier(mapping["name"], f"{label}.name")
        if name.casefold() in _FORBIDDEN_METADATA_KEYS:
            raise ValueError(f"{label}.name is forbidden in simulator-neutral IR: {name}")
        return cls(
            name=name,
            value=_scalar(mapping["value"], f"{label}.value"),
            unit=_optional_text(mapping.get("unit"), f"{label}.unit"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name, "value": self.value}
        if self.unit is not None:
            result["unit"] = self.unit
        return result


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    id: Identifier
    name: str | None = None
    formula: str | None = None
    cas: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str = "component") -> ComponentSpec:
        mapping = _object(data, label)
        _reject_unknown(mapping, {"id", "name", "formula", "cas"}, label)
        if "id" not in mapping:
            raise ValueError(f"{label} requires id")
        return cls(
            id=_identifier(mapping["id"], f"{label}.id"),
            name=_optional_text(mapping.get("name"), f"{label}.name"),
            formula=_optional_text(mapping.get("formula"), f"{label}.formula"),
            cas=_optional_text(mapping.get("cas"), f"{label}.cas"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id}
        for key, value in (("name", self.name), ("formula", self.formula), ("cas", self.cas)):
            if value is not None:
                result[key] = value
        return result


@dataclass(frozen=True, slots=True)
class PortSpec:
    id: Identifier
    direction: PortDirection
    required: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str = "port") -> PortSpec:
        mapping = _object(data, label)
        _reject_unknown(mapping, {"id", "direction", "required"}, label)
        if "id" not in mapping or "direction" not in mapping:
            raise ValueError(f"{label} requires id and direction")
        direction = _text(mapping["direction"], f"{label}.direction")
        if direction not in {"in", "out"}:
            raise ValueError(f"{label}.direction must be 'in' or 'out'")
        return cls(
            id=_identifier(mapping["id"], f"{label}.id"),
            direction=cast(PortDirection, direction),
            required=_boolean(mapping.get("required", True), f"{label}.required"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "direction": self.direction, "required": self.required}


@dataclass(frozen=True, slots=True)
class Endpoint:
    unit: Identifier
    port: Identifier

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str) -> Endpoint:
        mapping = _object(data, label)
        _reject_unknown(mapping, {"unit", "port"}, label)
        if "unit" not in mapping or "port" not in mapping:
            raise ValueError(f"{label} requires unit and port")
        return cls(
            unit=_identifier(mapping["unit"], f"{label}.unit"),
            port=_identifier(mapping["port"], f"{label}.port"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"unit": self.unit, "port": self.port}


@dataclass(frozen=True, slots=True)
class UnitOperationSpec:
    id: Identifier
    kind: str
    ports: tuple[PortSpec, ...]
    parameters: tuple[ParameterSpec, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str = "unit") -> UnitOperationSpec:
        mapping = _object(data, label)
        _reject_unknown(mapping, {"id", "kind", "ports", "parameters", "metadata"}, label)
        if "id" not in mapping or "kind" not in mapping:
            raise ValueError(f"{label} requires id and kind")
        ports = tuple(
            PortSpec.from_dict(
                _object(item, f"{label}.ports[{index}]"),
                label=f"{label}.ports[{index}]",
            )
            for index, item in enumerate(_array(mapping.get("ports", []), f"{label}.ports"))
        )
        parameters = tuple(
            ParameterSpec.from_dict(
                _object(item, f"{label}.parameters[{index}]"),
                label=f"{label}.parameters[{index}]",
            )
            for index, item in enumerate(
                _array(mapping.get("parameters", []), f"{label}.parameters")
            )
        )
        return cls(
            id=_identifier(mapping["id"], f"{label}.id"),
            kind=_text(mapping["kind"], f"{label}.kind").casefold(),
            ports=ports,
            parameters=parameters,
            metadata=_metadata(mapping.get("metadata", {}), f"{label}.metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "ports": [item.to_dict() for item in self.ports],
            "parameters": [item.to_dict() for item in self.parameters],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class StreamSpec:
    id: Identifier
    source: Endpoint
    target: Endpoint
    components: tuple[Identifier, ...] = ()
    parameters: tuple[ParameterSpec, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str = "stream") -> StreamSpec:
        mapping = _object(data, label)
        _reject_unknown(
            mapping,
            {"id", "source", "target", "components", "parameters", "metadata"},
            label,
        )
        if "id" not in mapping or "source" not in mapping or "target" not in mapping:
            raise ValueError(f"{label} requires id, source and target")
        components = tuple(
            _identifier(item, f"{label}.components[{index}]")
            for index, item in enumerate(
                _array(mapping.get("components", []), f"{label}.components")
            )
        )
        parameters = tuple(
            ParameterSpec.from_dict(
                _object(item, f"{label}.parameters[{index}]"),
                label=f"{label}.parameters[{index}]",
            )
            for index, item in enumerate(
                _array(mapping.get("parameters", []), f"{label}.parameters")
            )
        )
        return cls(
            id=_identifier(mapping["id"], f"{label}.id"),
            source=Endpoint.from_dict(
                _object(mapping["source"], f"{label}.source"),
                label=f"{label}.source",
            ),
            target=Endpoint.from_dict(
                _object(mapping["target"], f"{label}.target"),
                label=f"{label}.target",
            ),
            components=components,
            parameters=parameters,
            metadata=_metadata(mapping.get("metadata", {}), f"{label}.metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "components": list(self.components),
            "parameters": [item.to_dict() for item in self.parameters],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ProcessIntent:
    name: str
    components: tuple[ComponentSpec, ...]
    units: tuple[UnitOperationSpec, ...]
    streams: tuple[StreamSpec, ...]
    property_package: str | None = None
    schema: str = IR_SCHEMA
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProcessIntent:
        mapping = _object(data, "process intent")
        _reject_unknown(
            mapping,
            {"schema", "name", "property_package", "components", "units", "streams", "metadata"},
            "process intent",
        )
        if "name" not in mapping:
            raise ValueError("process intent requires name")
        schema = _text(mapping.get("schema", IR_SCHEMA), "process intent.schema")
        if schema != IR_SCHEMA:
            raise ValueError(f"Unsupported process intent schema: {schema}")
        components = tuple(
            ComponentSpec.from_dict(
                _object(item, f"components[{index}]"),
                label=f"components[{index}]",
            )
            for index, item in enumerate(_array(mapping.get("components", []), "components"))
        )
        units = tuple(
            UnitOperationSpec.from_dict(
                _object(item, f"units[{index}]"),
                label=f"units[{index}]",
            )
            for index, item in enumerate(_array(mapping.get("units", []), "units"))
        )
        streams = tuple(
            StreamSpec.from_dict(
                _object(item, f"streams[{index}]"),
                label=f"streams[{index}]",
            )
            for index, item in enumerate(_array(mapping.get("streams", []), "streams"))
        )
        return cls(
            name=_text(mapping["name"], "process intent.name"),
            components=components,
            units=units,
            streams=streams,
            property_package=_optional_text(
                mapping.get("property_package"),
                "process intent.property_package",
            ),
            schema=schema,
            metadata=_metadata(mapping.get("metadata", {}), "process intent.metadata"),
        )

    def normalized(self) -> ProcessIntent:
        units = tuple(
            UnitOperationSpec(
                id=unit.id,
                kind=unit.kind,
                ports=tuple(sorted(unit.ports, key=lambda item: (item.direction, item.id))),
                parameters=tuple(sorted(unit.parameters, key=lambda item: item.name)),
                metadata=dict(unit.metadata),
            )
            for unit in sorted(self.units, key=lambda item: item.id)
        )
        streams = tuple(
            StreamSpec(
                id=stream.id,
                source=stream.source,
                target=stream.target,
                components=tuple(sorted(stream.components)),
                parameters=tuple(sorted(stream.parameters, key=lambda item: item.name)),
                metadata=dict(stream.metadata),
            )
            for stream in sorted(self.streams, key=lambda item: item.id)
        )
        return ProcessIntent(
            name=self.name,
            components=tuple(sorted(self.components, key=lambda item: item.id)),
            units=units,
            streams=streams,
            property_package=self.property_package,
            schema=self.schema,
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "property_package": self.property_package,
            "components": [item.to_dict() for item in self.components],
            "units": [item.to_dict() for item in self.units],
            "streams": [item.to_dict() for item in self.streams],
            "metadata": dict(self.metadata),
        }

    def canonical_dict(self) -> dict[str, Any]:
        return self.normalized().to_dict()

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True, order=True)
class ValidationIssue:
    severity: IssueSeverity
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ValidationReport:
    valid: bool
    digest: str
    counts: dict[str, int]
    issues: tuple[ValidationIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "digest": self.digest,
            "counts": dict(self.counts),
            "issues": [item.to_dict() for item in self.issues],
        }


def validate_process_intent(
    intent: ProcessIntent,
    *,
    allow_recycles: bool = True,
) -> ValidationReport:
    from .process_ir_validation import validate_process_intent as _validate

    return _validate(intent, allow_recycles=allow_recycles)
