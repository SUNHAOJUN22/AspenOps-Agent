from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, StrEnum
from importlib import resources
from types import MappingProxyType
from typing import Any, Final, Iterable, Mapping, Sequence, cast

from aspenops_nexus.hashing import canonical_hash

COMMON_SCHEMA = "aspenops.research.common/v1"
_OBJECT_TYPES: Final[tuple[str, ...]] = (
    "study",
    "dataset",
    "target",
    "parameter",
    "assumption",
    "calibration",
    "validation",
    "claim",
)
_SCHEMA_FILES: Final[tuple[str, ...]] = (
    "common.schema.json",
    "study.schema.json",
    "dataset.schema.json",
    "target.schema.json",
    "parameter.schema.json",
    "assumption.schema.json",
    "calibration.schema.json",
    "validation.schema.json",
    "claim.schema.json",
)
_MATURITY_ORDER: Final[tuple[str, ...]] = (
    "STRUCTURE_ONLY",
    "SOURCE_CASE_REPRODUCED",
    "CALIBRATED_IN_DOMAIN",
    "VALIDATED_HELD_OUT",
    "ROBUSTNESS_TESTED",
    "LICENSED_ENGINEERING_REVIEWED",
)
_MATURITY_RANK: Final[Mapping[str, int]] = MappingProxyType(
    {value: index for index, value in enumerate(_MATURITY_ORDER)}
)
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TREE_PATH_PATTERN = re.compile(
    r"(?:\\(?:data|streams|blocks|flowsheeting options)\\|/data/|"
    r"tree\s*\.\s*findnode\s*\(|findnode\s*\()",
    re.IGNORECASE,
)
_EXECUTABLE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\b(?:eval|exec|compile)\s*\(", re.IGNORECASE),
    re.compile(r"\b(?:os\.system|subprocess\.|shell\s*=\s*true)\b", re.IGNORECASE),
    re.compile(r"\b(?:powershell|cmd\.exe|bash)\s+(?:-|/)", re.IGNORECASE),
    re.compile(r"\bpython(?:3(?:\.\d+)?)?\s+-c\b", re.IGNORECASE),
    re.compile(r"\b(?:createobject|getobject)\s*\(", re.IGNORECASE),
    re.compile(r"\bwscript\.shell\b", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*(?:sub|function)\s+[A-Za-z_]", re.IGNORECASE),
)
_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "aspen_tree_path",
        "code",
        "command",
        "com_progid",
        "executable",
        "macro",
        "powershell",
        "python",
        "script",
        "shell",
        "tree_path",
        "vba",
    }
)
ObjectKey = tuple[str, str, int]
JsonObject = dict[str, Any]


class ResearchGovernanceError(ValueError):
    """Raised when a P0 research governance invariant fails closed."""


class EvidenceGrade(StrEnum):
    REPRODUCTION = "reproduction"
    CALIBRATION = "calibration"
    VALIDATION = "validation"


class QualificationState(IntEnum):
    DRAFT = -1
    STRUCTURE_ONLY = 0
    SOURCE_CASE_REPRODUCED = 1
    CALIBRATED_IN_DOMAIN = 2
    VALIDATED_HELD_OUT = 3
    ROBUSTNESS_TESTED = 4
    LICENSED_ENGINEERING_REVIEWED = 5
    BLOCKED = 99


class GateOutcome(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    DOWNGRADE_REQUIRED = "DOWNGRADE_REQUIRED"


@dataclass(frozen=True, slots=True)
class GovernanceIssue:
    code: str
    message: str
    object_key: ObjectKey | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class GraphValidationReport:
    valid: bool
    object_count: int
    issues: tuple[GovernanceIssue, ...]
    graph_sha256: str


@dataclass(frozen=True, slots=True)
class ClaimGateDecision:
    outcome: GateOutcome
    requested_maturity: str
    maximum_maturity: str
    blockers: tuple[str, ...]
    evidence_grade: EvidenceGrade

    @property
    def allowed(self) -> bool:
        return self.outcome is GateOutcome.ALLOW


@dataclass(frozen=True, slots=True)
class SourceContradictionEntry:
    group: str
    assumption_refs: tuple[Mapping[str, Any], ...]
    unresolved: bool
    critical: bool
    restrictions: tuple[str, ...]


def schema_catalog() -> Mapping[str, JsonObject]:
    """Load the nine packaged JSON Schema 2020-12 contracts."""

    base = resources.files("aspenops_nexus.research").joinpath("schemas")
    catalog: dict[str, JsonObject] = {}
    for name in _SCHEMA_FILES:
        payload = cast(JsonObject, json.loads(base.joinpath(name).read_text(encoding="utf-8")))
        catalog[cast(str, payload["$id"])] = payload
    return MappingProxyType(catalog)


def _catalog_by_name() -> Mapping[str, JsonObject]:
    return MappingProxyType(
        {
            identifier.rsplit("/", 1)[-1]: schema
            for identifier, schema in schema_catalog().items()
        }
    )


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "non-json"


def _resolve_ref(
    ref: str,
    current: JsonObject,
    catalog: Mapping[str, JsonObject],
) -> tuple[JsonObject, JsonObject]:
    file_name, _, fragment = ref.partition("#")
    root = current if not file_name else catalog.get(file_name)
    if root is None:
        raise ResearchGovernanceError(f"unresolvable JSON Schema reference: {ref}")
    target: Any = root
    if fragment:
        if not fragment.startswith("/"):
            raise ResearchGovernanceError(f"unsupported JSON Schema fragment: {ref}")
        for token in fragment[1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or token not in target:
                raise ResearchGovernanceError(f"unresolvable JSON Schema fragment: {ref}")
            target = target[token]
    return cast(JsonObject, target), root


def _matches_schema(
    value: Any,
    schema: JsonObject,
    root: JsonObject,
    catalog: Mapping[str, JsonObject],
) -> bool:
    try:
        _validate_schema(value, schema, root, catalog, "$")
    except ResearchGovernanceError:
        return False
    return True


def _validate_schema(
    value: Any,
    schema: JsonObject,
    root: JsonObject,
    catalog: Mapping[str, JsonObject],
    path: str,
) -> None:
    if "$ref" in schema:
        target, target_root = _resolve_ref(cast(str, schema["$ref"]), root, catalog)
        _validate_schema(value, target, target_root, catalog, path)
    for item in cast(list[JsonObject], schema.get("allOf", [])):
        _validate_schema(value, item, root, catalog, path)
    for keyword, expected in (("anyOf", False), ("oneOf", True)):
        options = cast(list[JsonObject], schema.get(keyword, []))
        if options:
            matches = sum(_matches_schema(value, item, root, catalog) for item in options)
            if matches < 1 or (expected and matches != 1):
                raise ResearchGovernanceError(f"{path} does not satisfy {keyword}")
    if "not" in schema and _matches_schema(value, cast(JsonObject, schema["not"]), root, catalog):
        raise ResearchGovernanceError(f"{path} matches a forbidden JSON Schema condition")
    if "const" in schema and value != schema["const"]:
        raise ResearchGovernanceError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in cast(list[Any], schema["enum"]):
        raise ResearchGovernanceError(f"{path} contains an unsupported enum value")
    allowed_types = schema.get("type")
    if allowed_types is not None:
        names = (
            [allowed_types]
            if isinstance(allowed_types, str)
            else cast(list[str], allowed_types)
        )
        actual = _json_type(value)
        if actual == "integer" and "number" in names:
            actual = "number"
        if actual not in names:
            raise ResearchGovernanceError(f"{path} must have JSON type {names}")
    actual_type = _json_type(value)
    if actual_type in {"integer", "number"}:
        number = float(cast(int | float, value))
        if not math.isfinite(number):
            raise ResearchGovernanceError(f"{path} must be finite")
        if "minimum" in schema and number < float(schema["minimum"]):
            raise ResearchGovernanceError(f"{path} is below minimum")
        if "maximum" in schema and number > float(schema["maximum"]):
            raise ResearchGovernanceError(f"{path} exceeds maximum")
    elif actual_type == "string":
        text = cast(str, value)
        if len(text) < int(schema.get("minLength", 0)) or len(text) > int(
            schema.get("maxLength", 2**31)
        ):
            raise ResearchGovernanceError(f"{path} violates string length bounds")
        if "pattern" in schema and re.search(cast(str, schema["pattern"]), text) is None:
            raise ResearchGovernanceError(f"{path} does not match the required pattern")
        if schema.get("format") == "date-time":
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            try:
                parsed = datetime.fromisoformat(normalized)
            except ValueError as exc:
                raise ResearchGovernanceError(f"{path} must be RFC 3339 date-time") from exc
            if parsed.utcoffset() is None:
                raise ResearchGovernanceError(f"{path} must include a timezone")
    elif actual_type == "array":
        items = cast(list[Any], value)
        if len(items) < int(schema.get("minItems", 0)) or len(items) > int(
            schema.get("maxItems", 2**31)
        ):
            raise ResearchGovernanceError(f"{path} violates array size bounds")
        if schema.get("uniqueItems") and len(
            {canonical_hash(item) for item in items}
        ) != len(items):
            raise ResearchGovernanceError(f"{path} must contain unique items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(items):
                _validate_schema(
                    item,
                    cast(JsonObject, item_schema),
                    root,
                    catalog,
                    f"{path}[{index}]",
                )
    elif actual_type == "object":
        mapping = cast(JsonObject, value)
        if len(mapping) < int(schema.get("minProperties", 0)) or len(mapping) > int(
            schema.get("maxProperties", 2**31)
        ):
            raise ResearchGovernanceError(f"{path} violates object size bounds")
        required = set(cast(list[str], schema.get("required", [])))
        missing = sorted(required - set(mapping))
        if missing:
            raise ResearchGovernanceError(
                f"{path} is missing required fields: {', '.join(missing)}"
            )
        properties = cast(dict[str, JsonObject], schema.get("properties", {}))
        additional = schema.get("additionalProperties", True)
        for key, item in mapping.items():
            property_names = schema.get("propertyNames")
            if isinstance(property_names, dict):
                _validate_schema(
                    key,
                    cast(JsonObject, property_names),
                    root,
                    catalog,
                    f"{path} key",
                )
            if key in properties:
                _validate_schema(item, properties[key], root, catalog, f"{path}.{key}")
            elif additional is False:
                raise ResearchGovernanceError(f"{path} contains unsupported field: {key}")
            elif isinstance(additional, dict):
                _validate_schema(item, cast(JsonObject, additional), root, catalog, f"{path}.{key}")


def _object_type(document: Mapping[str, Any]) -> str:
    schema = document.get("schema")
    if (
        not isinstance(schema, str)
        or not schema.startswith("aspenops.research.")
        or not schema.endswith("/v1")
    ):
        raise ResearchGovernanceError("schema must be aspenops.research.<type>/v1")
    object_type = schema.removeprefix("aspenops.research.").removesuffix("/v1")
    if object_type not in _OBJECT_TYPES:
        raise ResearchGovernanceError(f"unsupported research object schema: {schema}")
    return object_type


def _scan_safe(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ResearchGovernanceError(f"{path} contains a non-finite number")
        return
    if isinstance(value, str):
        if "\x00" in value or "\r" in value:
            raise ResearchGovernanceError(f"{path} contains a forbidden control character")
        if _TREE_PATH_PATTERN.search(value):
            raise ResearchGovernanceError(f"{path} contains a raw simulator Tree Path")
        if any(pattern.search(value) for pattern in _EXECUTABLE_PATTERNS):
            raise ResearchGovernanceError(f"{path} contains executable code or a command")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_safe(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in _FORBIDDEN_KEYS:
                raise ResearchGovernanceError(f"{path} contains forbidden key: {key}")
            _scan_safe(item, f"{path}.{key}")
    elif value is not None and not isinstance(value, bool | int):
        raise ResearchGovernanceError(f"{path} contains a non-JSON value")


def canonical_content(value: Mapping[str, Any]) -> JsonObject:
    document = copy.deepcopy(dict(value))
    document.pop("content_sha256", None)
    document.pop("claim_sha256", None)
    return document


def content_sha256(value: Mapping[str, Any]) -> str:
    return canonical_hash(canonical_content(value))


def _claim_hash_payload(document: Mapping[str, Any]) -> JsonObject:
    keys = (
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
        "expires_at",
    )
    return {key: copy.deepcopy(document[key]) for key in keys if key in document}


def _ref_key(ref: Mapping[str, Any]) -> ObjectKey:
    return cast(str, ref["type"]), cast(str, ref["id"]), cast(int, ref["revision"])


def _semantic_invariants(document: JsonObject, object_type: str, *, sealed: bool) -> None:
    alias = f"{object_type}_id"
    if document[alias] != document["id"]:
        raise ResearchGovernanceError(f"{alias} must equal id")
    created = datetime.fromisoformat(cast(str, document["created_at"]).replace("Z", "+00:00"))
    updated = datetime.fromisoformat(cast(str, document["updated_at"]).replace("Z", "+00:00"))
    if updated < created:
        raise ResearchGovernanceError("updated_at must not precede created_at")
    if document.get("supersedes") is not None:
        ref = cast(JsonObject, document["supersedes"])
        if (
            ref["type"] != object_type
            or ref["id"] != document["id"]
            or ref["revision"] >= document["revision"]
        ):
            raise ResearchGovernanceError(
                "supersedes must reference an earlier revision of the same object"
            )

    if object_type == "study":
        if document["status"] != document["lifecycle_state"]:
            raise ResearchGovernanceError("study.status must equal lifecycle_state")
        backend = cast(JsonObject, document["backend_policy"])
        if "mock" in backend["allowed_backends"] and not backend["mock_allowed"]:
            raise ResearchGovernanceError("mock backend requires mock_allowed=true")
        if not document["calibration_validation_policy"]["record_isolation_required"]:
            raise ResearchGovernanceError(
                "Study must require Calibration/Validation record isolation"
            )
    elif object_type == "dataset":
        if document["kind"] in {"derived", "soft_sensor"} and not document.get("lineage"):
            raise ResearchGovernanceError("derived and soft_sensor Dataset require lineage")
        if (
            document["role"] in {"calibration", "validation", "stress_test"}
            and not document["record_fingerprints"]
        ):
            raise ResearchGovernanceError("evidence Dataset requires record_fingerprints")
        names = [item["name"] for item in document["variables"]]
        if len(names) != len(set(names)):
            raise ResearchGovernanceError("Dataset variable names must be unique")
        uncertainty = cast(JsonObject, document["measurement_uncertainty"])
        if uncertainty["status"] == "known" and not {"kind", "value", "unit"}.issubset(uncertainty):
            raise ResearchGovernanceError(
                "known measurement uncertainty requires kind, value and unit"
            )
    elif object_type == "parameter":
        if document["mode"] == "estimated":
            bounds = document.get("bounds")
            if not isinstance(bounds, dict) or float(bounds["lower"]) >= float(bounds["upper"]):
                raise ResearchGovernanceError("estimated Parameter requires finite ordered bounds")
        if document["sharing_scope"] in {
            "grade_specific",
            "reactor_specific",
        } and not document.get("local_scope_exception"):
            raise ResearchGovernanceError(
                "local Parameter scope requires explicit exception evidence"
            )
    elif object_type == "assumption":
        if document["category"] == "source_contradiction":
            if not document.get("contradiction_group") or len(document["evidence_refs"]) < 2:
                raise ResearchGovernanceError(
                    "source contradiction requires a group and competing evidence"
                )
        if (
            document["risk"] == "critical"
            and document["status"] == "unresolved"
            and not document["claim_restrictions"]
        ):
            raise ResearchGovernanceError("unresolved critical Assumption must restrict Claim")
    elif object_type == "calibration":
        plan = cast(JsonObject, document["execution_plan"])
        if plan != {
            "mode": "governance_only",
            "approved": False,
            "request_refs": [],
            "contains_executable_code": False,
        }:
            raise ResearchGovernanceError(
                "P0 Calibration execution_plan must remain governance-only"
            )
        proof = cast(JsonObject, document["data_split_proof"])
        overlap = set(proof["calibration_record_fingerprints"]) & set(
            proof["validation_record_fingerprints"]
        )
        if overlap or proof["overlap_count"] != len(overlap) or not proof["verified"]:
            raise ResearchGovernanceError("Calibration data_split_proof must prove zero overlap")
        if document["status"] == "accepted" and not document.get("accepted_parameter_snapshot"):
            raise ResearchGovernanceError(
                "accepted Calibration requires an immutable parameter snapshot"
            )
    elif object_type == "validation":
        if document["parameter_snapshot"].get("source_calibration") != document["calibration_ref"]:
            raise ResearchGovernanceError(
                "Validation parameter snapshot must bind the exact Calibration"
            )
        if document["execution_policy"]["parameter_adjustment_allowed"]:
            raise ResearchGovernanceError("Validation must not adjust parameters")
        leakage = cast(JsonObject, document["leakage_check"])
        overlap = set(leakage["calibration_record_fingerprints"]) & set(
            leakage["validation_record_fingerprints"]
        )
        if overlap or leakage["overlap_count"] != len(overlap) or not leakage["passed"]:
            raise ResearchGovernanceError("Validation leakage_check must prove zero overlap")
        blockers = cast(list[str], document["blockers"])
        if document["status"] == "passed" and (
            blockers or not document.get("claim_ceiling_result")
        ):
            raise ResearchGovernanceError(
                "passed Validation requires no blockers and a Claim ceiling"
            )
        if document["status"] in {"failed", "incomplete", "blocked"} and not blockers:
            raise ResearchGovernanceError(
                "failed/incomplete/blocked Validation must list real blockers"
            )
    elif object_type == "claim":
        maturity = cast(str, document["maturity"])
        if document["claim_type"] == "structure" and maturity != "STRUCTURE_ONLY":
            raise ResearchGovernanceError("structure Claim must be STRUCTURE_ONLY")
        if document["claim_type"] == "source_reproduction" and _MATURITY_RANK[maturity] > 1:
            raise ResearchGovernanceError(
                "source reproduction Claim cannot become calibration or validation"
            )
        if sealed and document.get("claim_sha256") != canonical_hash(_claim_hash_payload(document)):
            raise ResearchGovernanceError("claim_sha256 does not match canonical Claim content")

    if sealed:
        digest = document.get("content_sha256")
        if not isinstance(digest, str) or _SHA256_PATTERN.fullmatch(digest) is None:
            raise ResearchGovernanceError("sealed object requires content_sha256")
        if digest != content_sha256(document):
            raise ResearchGovernanceError(
                "content_sha256 does not match canonical immutable content"
            )


def validate_object(value: Any, *, sealed: bool = False) -> JsonObject:
    """Validate one strict P0 manifest without invoking Aspen or the execution plane."""

    if not isinstance(value, dict):
        raise ResearchGovernanceError("research object must be a JSON object")
    document = copy.deepcopy(cast(JsonObject, value))
    object_type = _object_type(document)
    _scan_safe(document)
    catalog = _catalog_by_name()
    schema = catalog[f"{object_type}.schema.json"]
    _validate_schema(document, schema, schema, catalog, "$")
    _semantic_invariants(document, object_type, sealed=sealed)
    return document


def seal_object(value: Mapping[str, Any]) -> JsonObject:
    """Validate and add deterministic derived hashes to an immutable revision."""

    document = copy.deepcopy(dict(value))
    document.pop("content_sha256", None)
    document.pop("claim_sha256", None)
    validate_object(document)
    if _object_type(document) == "claim":
        document["claim_sha256"] = canonical_hash(_claim_hash_payload(document))
    document["content_sha256"] = content_sha256(document)
    return validate_object(document, sealed=True)


def immutable_ref(value: Mapping[str, Any]) -> JsonObject:
    document = validate_object(value, sealed=True)
    return {
        "type": _object_type(document),
        "id": document["id"],
        "revision": document["revision"],
        "sha256": document["content_sha256"],
    }


def _object_key(value: Mapping[str, Any]) -> ObjectKey:
    return _object_type(value), cast(str, value["id"]), cast(int, value["revision"])


def _iter_refs(value: Any, path: str = "$") -> Iterable[tuple[str, JsonObject]]:
    if isinstance(value, dict):
        if set(value) == {"type", "id", "revision", "sha256"}:
            yield path, cast(JsonObject, value)
        else:
            for key, item in value.items():
                if isinstance(item, dict | list):
                    yield from _iter_refs(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_refs(item, f"{path}[{index}]")


class ResearchGraph:
    """Immutable P0 graph with references, leakage, snapshots and Claim gates."""

    def __init__(self, objects: Sequence[Mapping[str, Any]]) -> None:
        validated: dict[ObjectKey, JsonObject] = {}
        for item in objects:
            document = validate_object(item, sealed=True)
            key = _object_key(document)
            if key in validated:
                raise ResearchGovernanceError(f"duplicate research object: {key}")
            validated[key] = document
        self._objects: Mapping[ObjectKey, JsonObject] = MappingProxyType(validated)

    @property
    def objects(self) -> Mapping[ObjectKey, JsonObject]:
        return self._objects

    def get(self, ref: Mapping[str, Any]) -> JsonObject:
        key = _ref_key(ref)
        target = self._objects.get(key)
        if target is None:
            raise ResearchGovernanceError(f"ObjectRef target does not exist: {key}")
        if target["content_sha256"] != ref.get("sha256"):
            raise ResearchGovernanceError(f"ObjectRef hash mismatch: {key}")
        return copy.deepcopy(target)

    def of_type(self, object_type: str) -> tuple[JsonObject, ...]:
        if object_type not in _OBJECT_TYPES:
            raise ResearchGovernanceError(f"unknown object type: {object_type}")
        return tuple(
            copy.deepcopy(value)
            for key, value in self._objects.items()
            if key[0] == object_type
        )

    def validate(self) -> GraphValidationReport:
        issues: list[GovernanceIssue] = []
        for key, document in self._objects.items():
            for path, ref in _iter_refs(document):
                target = self._objects.get(_ref_key(ref))
                if target is None:
                    issues.append(
                        GovernanceIssue(
                            "reference.missing",
                            "referenced object does not exist",
                            key,
                            path,
                        )
                    )
                elif target["content_sha256"] != ref["sha256"]:
                    issues.append(
                        GovernanceIssue(
                            "reference.hash_mismatch",
                            "referenced object hash does not match",
                            key,
                            path,
                        )
                    )
        issues.extend(self._relationship_issues())
        issues.extend(self._leakage_issues())
        payload = [
            {"key": list(key), "sha256": document["content_sha256"]}
            for key, document in sorted(self._objects.items())
        ]
        return GraphValidationReport(
            not issues,
            len(self._objects),
            tuple(issues),
            canonical_hash(payload),
        )

    def require_valid(self) -> GraphValidationReport:
        report = self.validate()
        if not report.valid:
            detail = "; ".join(f"{item.code}: {item.message}" for item in report.issues)
            raise ResearchGovernanceError(f"research graph is invalid: {detail}")
        return report

    def _relationship_issues(self) -> list[GovernanceIssue]:
        issues: list[GovernanceIssue] = []
        for key, document in self._objects.items():
            if key[0] == "calibration":
                for index, ref in enumerate(document["dataset_refs"]):
                    target = self._objects.get(_ref_key(ref))
                    if target is not None and target.get("role") != "calibration":
                        issues.append(
                            GovernanceIssue(
                                "calibration.dataset_role",
                                "Calibration requires calibration-role Dataset",
                                key,
                                f"$.dataset_refs[{index}]",
                            )
                        )
                for index, ref in enumerate(document["parameter_refs"]):
                    target = self._objects.get(_ref_key(ref))
                    if target is not None and target.get("mode") != "estimated":
                        issues.append(
                            GovernanceIssue(
                                "calibration.parameter_mode",
                                "Calibration requires estimated Parameter",
                                key,
                                f"$.parameter_refs[{index}]",
                            )
                        )
            elif key[0] == "validation":
                for index, ref in enumerate(document["dataset_refs"]):
                    target = self._objects.get(_ref_key(ref))
                    if target is not None and target.get("role") not in {
                        "validation",
                        "stress_test",
                    }:
                        issues.append(
                            GovernanceIssue(
                                "validation.dataset_role",
                                "Validation requires validation/stress_test Dataset",
                                key,
                                f"$.dataset_refs[{index}]",
                            )
                        )
                calibration = self._objects.get(_ref_key(document["calibration_ref"]))
                if calibration is not None:
                    if calibration.get("status") != "accepted":
                        issues.append(
                            GovernanceIssue(
                                "validation.calibration_not_accepted",
                                "Validation must bind accepted Calibration",
                                key,
                                "$.calibration_ref",
                            )
                        )
                    accepted = calibration.get("accepted_parameter_snapshot")
                    if not isinstance(accepted, dict) or accepted.get(
                        "sha256"
                    ) != document["parameter_snapshot"].get("sha256"):
                        issues.append(
                            GovernanceIssue(
                                "validation.snapshot_mismatch",
                                "Validation must use accepted immutable parameter snapshot",
                                key,
                                "$.parameter_snapshot",
                            )
                        )
            elif key[0] == "study":
                listed = {
                    _ref_key(ref)
                    for refs in document["object_refs"].values()
                    for ref in refs
                }
                expected = {candidate for candidate in self._objects if candidate[0] != "study"}
                if listed != expected:
                    issues.append(
                        GovernanceIssue(
                            "study.object_index",
                            "Study object_refs must exactly index its graph",
                            key,
                            "$.object_refs",
                        )
                    )
        return issues

    def _datasets_for(self, object_type: str) -> tuple[JsonObject, ...]:
        datasets: list[JsonObject] = []
        for key, document in self._objects.items():
            if key[0] == object_type:
                for ref in document.get("dataset_refs", []):
                    target = self._objects.get(_ref_key(ref))
                    if target is not None:
                        datasets.append(target)
        return tuple(datasets)

    def _leakage_issues(self) -> list[GovernanceIssue]:
        calibration = self._datasets_for("calibration")
        validation = self._datasets_for("validation")
        cal_records = {record for item in calibration for record in item["record_fingerprints"]}
        val_records = {record for item in validation for record in item["record_fingerprints"]}
        cal_groups = {item.get("split_group") for item in calibration if item.get("split_group")}
        val_groups = {item.get("split_group") for item in validation if item.get("split_group")}
        issues: list[GovernanceIssue] = []
        if overlap := sorted(cal_records & val_records):
            issues.append(
                GovernanceIssue(
                    "data.leakage_record",
                    f"record overlap: {', '.join(overlap[:5])}",
                )
            )
        if overlap := sorted(cal_groups & val_groups):
            issues.append(
                GovernanceIssue(
                    "data.leakage_split_group",
                    f"split_group overlap: {', '.join(overlap)}",
                )
            )
        return issues

    def source_contradictions(self) -> tuple[SourceContradictionEntry, ...]:
        groups: dict[str, list[JsonObject]] = {}
        for item in self.of_type("assumption"):
            if item["category"] == "source_contradiction":
                groups.setdefault(cast(str, item["contradiction_group"]), []).append(item)
        return tuple(
            SourceContradictionEntry(
                group,
                tuple(immutable_ref(item) for item in items),
                any(item["status"] in {"unresolved", "challenged"} for item in items),
                any(item["risk"] == "critical" for item in items),
                tuple(sorted({text for item in items for text in item["claim_restrictions"]})),
            )
            for group, items in sorted(groups.items())
        )

    def _single_study(self) -> JsonObject:
        studies = self.of_type("study")
        if len(studies) != 1:
            raise ResearchGovernanceError("Claim gate requires exactly one Study")
        return studies[0]

    def claim_gate(self, claim_ref: Mapping[str, Any]) -> ClaimGateDecision:
        report = self.validate()
        claim = self.get(claim_ref)
        if _object_type(claim) != "claim":
            raise ResearchGovernanceError("claim_gate requires a Claim reference")
        study = self._single_study()
        requested = cast(str, claim["maturity"])
        ceiling = _MATURITY_RANK[cast(str, study["claim_ceiling"])]
        blockers = [f"{item.code}: {item.message}" for item in report.issues]
        if study["lifecycle_state"] not in {"validated", "claim_ready"}:
            blockers.append("Study must be validated or claim_ready")
        if _MATURITY_RANK[requested] > ceiling:
            blockers.append("Claim exceeds Study claim_ceiling")
        if study["purpose"] == "source_reproduction":
            ceiling = min(ceiling, 1)
            if _MATURITY_RANK[requested] > ceiling:
                blockers.append(
                    "Source reproduction cannot become calibration or independent validation"
                )
        backends = set(study["backend_policy"]["allowed_backends"])
        if "mock" in backends and not backends & {"aspen_plus", "aspen_hysys"}:
            ceiling = min(ceiling, 0)
            if _MATURITY_RANK[requested] > ceiling:
                blockers.append("Mock-only evidence cannot support real engineering qualification")
        domain = cast(JsonObject, study["domain"])
        if (
            str(domain.get("polymer_system", "")).upper() == "EPDM"
            and domain.get("evidence_boundary") == "components_properties_only"
        ):
            ceiling = min(ceiling, 0)
            if _MATURITY_RANK[requested] > ceiling:
                blockers.append("EPDM components/properties example is limited to STRUCTURE_ONLY")
        assumptions = [self.get(ref) for ref in claim["assumption_refs"]]
        for assumption in assumptions:
            if assumption["risk"] == "critical" and assumption["status"] == "unresolved":
                ceiling = min(ceiling, 0)
                blockers.append(
                    f"Unresolved critical Assumption restricts Claim: {assumption['id']}"
                )
        validations = [self.get(ref) for ref in claim["validation_refs"]]
        if _MATURITY_RANK[requested] >= 3:
            if not validations or any(item["status"] != "passed" for item in validations):
                blockers.append("VALIDATED_HELD_OUT or higher requires passed Validation")
            if requested == "VALIDATED_HELD_OUT" and not any(
                item["validation_type"]
                in {"heldout_grade", "heldout_time", "cross_reactor"}
                for item in validations
            ):
                blockers.append("VALIDATED_HELD_OUT requires held-out evidence")
        if _MATURITY_RANK[requested] >= 4 and not any(
            item["status"] == "passed"
            and item["validation_type"] in {"stress_test", "out_of_domain"}
            for item in validations
        ):
            blockers.append("ROBUSTNESS_TESTED requires stress/out-of-domain evidence")
        if requested == "LICENSED_ENGINEERING_REVIEWED":
            real = any(
                item["status"] == "passed"
                and item["validation_type"] == "external"
                and item["execution_policy"]["backend"]
                in {"aspen_plus", "aspen_hysys"}
                for item in validations
            )
            if (
                not real
                or not claim["review"]["engineering_accepted"]
                or not claim["review"].get("approval_refs")
            ):
                blockers.append(
                    "Licensed engineering review requires real-backend external evidence "
                    "and approval"
                )
        if _MATURITY_RANK[requested] >= 2:
            calibrations = [
                self.get(ref)
                for ref in claim["evidence_refs"]
                if ref["type"] == "calibration"
            ]
            if not calibrations or any(item["status"] != "accepted" for item in calibrations):
                blockers.append("CALIBRATED_IN_DOMAIN or higher requires accepted Calibration")
        if claim["status"] in {"supported", "qualified"} and blockers:
            blockers.append("A blocked Claim cannot retain supported/qualified status")
        outcome = GateOutcome.ALLOW
        if blockers:
            outcome = (
                GateOutcome.DOWNGRADE_REQUIRED
                if _MATURITY_RANK[requested] > ceiling
                else GateOutcome.BLOCK
            )
        return ClaimGateDecision(
            outcome,
            requested,
            _MATURITY_ORDER[max(0, ceiling)],
            tuple(dict.fromkeys(blockers)),
            evidence_grade(study),
        )


def evidence_grade(study: Mapping[str, Any]) -> EvidenceGrade:
    purpose = study["purpose"]
    if purpose == "source_reproduction":
        return EvidenceGrade.REPRODUCTION
    if purpose in {"calibration", "sensitivity", "design_specification", "optimization"}:
        return EvidenceGrade.CALIBRATION
    return EvidenceGrade.VALIDATION


def can_transition_qualification(
    current: QualificationState,
    requested: QualificationState,
    *,
    study_purpose: str,
    gate_allowed: bool,
) -> bool:
    """Enforce a monotone, evidence-gated qualification state machine."""

    if requested is QualificationState.BLOCKED:
        return True
    if current is QualificationState.BLOCKED:
        return requested is QualificationState.DRAFT
    if requested.value != current.value + 1:
        return False
    if not gate_allowed and requested is not QualificationState.STRUCTURE_ONLY:
        return False
    return not (
        study_purpose == "source_reproduction"
        and requested.value > QualificationState.SOURCE_CASE_REPRODUCED.value
    )
