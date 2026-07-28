from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Literal, cast

RESEARCH_SCHEMA = "aspenops.research-study/v1"
MAX_DOCUMENT_BYTES = 4_194_304
MAX_JSON_DEPTH = 12

ResearchObjectType = Literal[
    "study",
    "dataset",
    "target",
    "parameter",
    "assumption",
    "calibration",
    "validation",
    "claim",
]
Maturity = Literal[
    "STRUCTURE_ONLY",
    "SOURCE_CASE_REPRODUCED",
    "CALIBRATED_IN_DOMAIN",
    "VALIDATED_HELD_OUT",
    "ROBUSTNESS_TESTED",
    "LICENSED_ENGINEERING_REVIEWED",
]
IssueSeverity = Literal["error", "warning"]

_OBJECT_TYPES: tuple[ResearchObjectType, ...] = (
    "study",
    "dataset",
    "target",
    "parameter",
    "assumption",
    "calibration",
    "validation",
    "claim",
)
_ID_PATTERN = re.compile(
    r"^(study|dataset|target|parameter|assumption|calibration|validation|claim)\."
    r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SEMANTIC_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_FORBIDDEN_KEYS = {
    "aspen_tree_path",
    "code",
    "com_path",
    "command",
    "exec",
    "python",
    "script",
    "shell",
    "tree_path",
    "vba",
}
_MATURITY_RANK = {
    "STRUCTURE_ONLY": 0,
    "SOURCE_CASE_REPRODUCED": 1,
    "CALIBRATED_IN_DOMAIN": 2,
    "VALIDATED_HELD_OUT": 3,
    "ROBUSTNESS_TESTED": 4,
    "LICENSED_ENGINEERING_REVIEWED": 5,
}
_LIFECYCLE_RANK = {
    "draft": 0,
    "specified": 1,
    "data_ready": 2,
    "calibration_ready": 3,
    "calibrated": 4,
    "validation_ready": 5,
    "validated": 6,
    "claim_ready": 7,
    "blocked": 8,
    "archived": 9,
}


class ResearchValidationError(ValueError):
    """Raised when a Research Study document violates a structural contract."""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ResearchValidationError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ResearchValidationError(f"{label} must be an array")
    return value


def _text(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise ResearchValidationError(f"{label} must be a string")
    normalized = value.strip()
    if nonempty and not normalized:
        raise ResearchValidationError(f"{label} must be a non-empty string")
    if any(character in normalized for character in ("\x00", "\r", "\n")):
        raise ResearchValidationError(f"{label} must be one safe text line")
    return normalized


def _optional_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ResearchValidationError(f"{label} must be a boolean")
    return value


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ResearchValidationError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ResearchValidationError(f"{label} must be a finite number")
    return number


def _scalar(value: Any, label: str) -> str | int | float | bool:
    if isinstance(value, bool | str | int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ResearchValidationError(f"{label} must be a finite scalar JSON value")


def _enum(value: Any, allowed: set[str], label: str) -> str:
    normalized = _text(value, label)
    if normalized not in allowed:
        raise ResearchValidationError(
            f"{label} must be one of: {', '.join(sorted(allowed))}"
        )
    return normalized


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ResearchValidationError(
            f"{label} contains unsupported fields: {', '.join(unknown)}"
        )


def _safe_json(value: Any, label: str, *, depth: int = 0) -> Any:
    if depth > MAX_JSON_DEPTH:
        raise ResearchValidationError(
            f"{label} exceeds maximum JSON nesting depth {MAX_JSON_DEPTH}"
        )
    if value is None or isinstance(value, bool | str | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ResearchValidationError(f"{label} contains a non-finite number")
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
            if key.casefold() in _FORBIDDEN_KEYS:
                raise ResearchValidationError(f"{label} contains forbidden key: {key}")
            result[key] = _safe_json(item, f"{label}.{key}", depth=depth + 1)
        return result
    raise ResearchValidationError(f"{label} contains a non-JSON value")


def _json_object(value: Any, label: str) -> dict[str, Any]:
    return cast(dict[str, Any], _safe_json(_mapping(value, label), label))


def _strings(value: Any, label: str, *, nonempty: bool = False) -> tuple[str, ...]:
    items = tuple(
        _text(item, f"{label}[{index}]")
        for index, item in enumerate(_sequence(value, label))
    )
    if nonempty and not items:
        raise ResearchValidationError(f"{label} must contain at least one value")
    if len(set(items)) != len(items):
        raise ResearchValidationError(f"{label} must not contain duplicates")
    return items


def _id(value: Any, expected_type: ResearchObjectType, label: str) -> str:
    identifier = _text(value, label)
    match = _ID_PATTERN.fullmatch(identifier)
    if match is None or match.group(1) != expected_type:
        raise ResearchValidationError(
            f"{label} must use the {expected_type}. prefix and a safe identifier"
        )
    return identifier


def _optional_sha256(value: Any, label: str) -> str | None:
    if value is None:
        return None
    digest = _text(value, label).lower()
    if _SHA256_PATTERN.fullmatch(digest) is None:
        raise ResearchValidationError(f"{label} must be a lowercase SHA-256 digest")
    return digest


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class ObjectRef:
    object_type: ResearchObjectType
    object_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str = "object_ref") -> ObjectRef:
        mapping = _mapping(data, label)
        _reject_unknown(mapping, {"type", "id"}, label)
        object_type = cast(
            ResearchObjectType,
            _enum(mapping.get("type"), set(_OBJECT_TYPES), f"{label}.type"),
        )
        return cls(
            object_type=object_type,
            object_id=_id(mapping.get("id"), object_type, f"{label}.id"),
        )

    def to_dict(self) -> dict[str, str]:
        return {"type": self.object_type, "id": self.object_id}


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    uri: str
    sha256: str
    media_type: str | None = None
    producer: ObjectRef | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str = "artifact_ref") -> ArtifactRef:
        mapping = _mapping(data, label)
        _reject_unknown(mapping, {"uri", "sha256", "media_type", "producer"}, label)
        uri = _text(mapping.get("uri"), f"{label}.uri")
        if uri.startswith(("http://", "https://")):
            raise ResearchValidationError(
                f"{label}.uri must be an immutable artifact identifier, not a mutable web URL"
            )
        digest = _optional_sha256(mapping.get("sha256"), f"{label}.sha256")
        if digest is None:
            raise ResearchValidationError(f"{label}.sha256 is required")
        producer_value = mapping.get("producer")
        producer = (
            None
            if producer_value is None
            else ObjectRef.from_dict(
                _mapping(producer_value, f"{label}.producer"),
                label=f"{label}.producer",
            )
        )
        return cls(
            uri=uri,
            sha256=digest,
            media_type=_optional_text(mapping.get("media_type"), f"{label}.media_type"),
            producer=producer,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"uri": self.uri, "sha256": self.sha256}
        if self.media_type is not None:
            result["media_type"] = self.media_type
        if self.producer is not None:
            result["producer"] = self.producer.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class SemanticBinding:
    key: str
    identifiers: dict[str, str]
    access: Literal["read", "write"]
    unit: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str) -> SemanticBinding:
        mapping = _mapping(data, label)
        _reject_unknown(mapping, {"key", "identifiers", "access", "unit"}, label)
        key = _text(mapping.get("key"), f"{label}.key")
        if _SEMANTIC_KEY_PATTERN.fullmatch(key) is None:
            raise ResearchValidationError(
                f"{label}.key must be a semantic Registry key, not a raw simulator path"
            )
        access = cast(
            Literal["read", "write"],
            _enum(mapping.get("access"), {"read", "write"}, f"{label}.access"),
        )
        raw_identifiers = _mapping(mapping.get("identifiers", {}), f"{label}.identifiers")
        identifiers = {
            _text(raw_key, f"{label}.identifiers key"): _text(
                raw_value, f"{label}.identifiers.{raw_key}"
            )
            for raw_key, raw_value in raw_identifiers.items()
        }
        return cls(
            key=key,
            identifiers=identifiers,
            access=access,
            unit=_optional_text(mapping.get("unit"), f"{label}.unit"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "key": self.key,
            "identifiers": dict(self.identifiers),
            "access": self.access,
        }
        if self.unit is not None:
            result["unit"] = self.unit
        return result


@dataclass(frozen=True, slots=True)
class SourceRef:
    source_id: str
    kind: Literal["literature", "plant", "laboratory", "model", "expert", "other"]
    citation: str
    locator: str | None = None
    sha256: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, label: str) -> SourceRef:
        mapping = _mapping(data, label)
        _reject_unknown(
            mapping,
            {"source_id", "kind", "citation", "locator", "sha256"},
            label,
        )
        kind = cast(
            Literal["literature", "plant", "laboratory", "model", "expert", "other"],
            _enum(
                mapping.get("kind"),
                {"literature", "plant", "laboratory", "model", "expert", "other"},
                f"{label}.kind",
            ),
        )
        return cls(
            source_id=_text(mapping.get("source_id"), f"{label}.source_id"),
            kind=kind,
            citation=_text(mapping.get("citation"), f"{label}.citation"),
            locator=_optional_text(mapping.get("locator"), f"{label}.locator"),
            sha256=_optional_sha256(mapping.get("sha256"), f"{label}.sha256"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "source_id": self.source_id,
            "kind": self.kind,
            "citation": self.citation,
        }
        if self.locator is not None:
            result["locator"] = self.locator
        if self.sha256 is not None:
            result["sha256"] = self.sha256
        return result


def _refs(value: Any, label: str, *, nonempty: bool = False) -> tuple[ObjectRef, ...]:
    refs = tuple(
        ObjectRef.from_dict(_mapping(item, f"{label}[{index}]"), label=f"{label}[{index}]")
        for index, item in enumerate(_sequence(value, label))
    )
    if nonempty and not refs:
        raise ResearchValidationError(f"{label} must contain at least one reference")
    identities = {(item.object_type, item.object_id) for item in refs}
    if len(identities) != len(refs):
        raise ResearchValidationError(f"{label} must not contain duplicate references")
    return refs


def _sources(value: Any, label: str, *, nonempty: bool = False) -> tuple[SourceRef, ...]:
    sources = tuple(
        SourceRef.from_dict(_mapping(item, f"{label}[{index}]"), label=f"{label}[{index}]")
        for index, item in enumerate(_sequence(value, label))
    )
    if nonempty and not sources:
        raise ResearchValidationError(f"{label} must contain at least one source")
    identifiers = [item.source_id for item in sources]
    if len(set(identifiers)) != len(identifiers):
        raise ResearchValidationError(f"{label} source_id values must be unique")
    return sources
