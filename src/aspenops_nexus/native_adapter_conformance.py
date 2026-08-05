from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, cast

from .compilation_plan import CompilationPlan

MANIFEST_SCHEMA = "aspenops.native-adapter-manifest/v1"
REPORT_SCHEMA = "aspenops.native-adapter-conformance-report/v1"

FailureIsolation = Literal["PRIVATE_CASE_DISCARD", "TRANSACTIONAL_ROLLBACK"]
_ALLOWED_FAILURE_ISOLATION = {"PRIVATE_CASE_DISCARD", "TRANSACTIONAL_ROLLBACK"}
_TOPOLOGY_OPERATIONS = {"readback_topology", "readback_topology_after_reopen"}
_LAYOUT_OPERATIONS = {"readback_layout", "readback_layout_after_reopen"}
_SAVE_REOPEN_OPERATIONS = {
    "save_case",
    "reopen_case",
    "readback_topology_after_reopen",
    "readback_layout_after_reopen",
}


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _sha256(value: Any, label: str) -> str:
    text = _text(value, label).casefold()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a 64-character lowercase hexadecimal SHA-256")
    return text


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a Boolean")
    return value


def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError(f"{label} must be an array")
    result = tuple(sorted(_text(item, f"{label} item") for item in value))
    if not result:
        raise ValueError(f"{label} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must contain unique values")
    return result


@dataclass(frozen=True, slots=True)
class NativeAdapterManifest:
    profile_id: str
    profile_sha256: str
    adapter_contract: str
    adapter_code_sha256: str
    runtime_identity_sha256: str
    supported_operations: tuple[str, ...]
    supported_adapter_keys: tuple[str, ...]
    supports_topology_readback: bool
    supports_layout_readback: bool
    supports_save_reopen: bool
    failure_isolation: FailureIsolation
    source_boundary: str
    schema: str = MANIFEST_SCHEMA

    @classmethod
    def from_dict(cls, value: Any) -> NativeAdapterManifest:
        if not isinstance(value, dict):
            raise ValueError("native adapter manifest must be an object")
        allowed = {
            "schema",
            "profile_id",
            "profile_sha256",
            "adapter_contract",
            "adapter_code_sha256",
            "runtime_identity_sha256",
            "supported_operations",
            "supported_adapter_keys",
            "supports_topology_readback",
            "supports_layout_readback",
            "supports_save_reopen",
            "failure_isolation",
            "source_boundary",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(
                "native adapter manifest contains unsupported fields: " + ", ".join(unknown)
            )
        schema = _text(value.get("schema", MANIFEST_SCHEMA), "manifest.schema")
        if schema != MANIFEST_SCHEMA:
            raise ValueError(f"Unsupported native adapter manifest schema: {schema}")
        isolation = _text(value.get("failure_isolation"), "manifest.failure_isolation")
        if isolation not in _ALLOWED_FAILURE_ISOLATION:
            raise ValueError(f"Unsupported failure isolation contract: {isolation}")
        return cls(
            profile_id=_text(value.get("profile_id"), "manifest.profile_id"),
            profile_sha256=_sha256(value.get("profile_sha256"), "manifest.profile_sha256"),
            adapter_contract=_text(value.get("adapter_contract"), "manifest.adapter_contract"),
            adapter_code_sha256=_sha256(
                value.get("adapter_code_sha256"),
                "manifest.adapter_code_sha256",
            ),
            runtime_identity_sha256=_sha256(
                value.get("runtime_identity_sha256"),
                "manifest.runtime_identity_sha256",
            ),
            supported_operations=_string_tuple(
                value.get("supported_operations"),
                "manifest.supported_operations",
            ),
            supported_adapter_keys=_string_tuple(
                value.get("supported_adapter_keys"),
                "manifest.supported_adapter_keys",
            ),
            supports_topology_readback=_bool(
                value.get("supports_topology_readback"),
                "manifest.supports_topology_readback",
            ),
            supports_layout_readback=_bool(
                value.get("supports_layout_readback"),
                "manifest.supports_layout_readback",
            ),
            supports_save_reopen=_bool(
                value.get("supports_save_reopen"),
                "manifest.supports_save_reopen",
            ),
            failure_isolation=cast(FailureIsolation, isolation),
            source_boundary=_text(value.get("source_boundary"), "manifest.source_boundary"),
            schema=schema,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_sha256,
            "adapter_contract": self.adapter_contract,
            "adapter_code_sha256": self.adapter_code_sha256,
            "runtime_identity_sha256": self.runtime_identity_sha256,
            "supported_operations": list(self.supported_operations),
            "supported_adapter_keys": list(self.supported_adapter_keys),
            "supports_topology_readback": self.supports_topology_readback,
            "supports_layout_readback": self.supports_layout_readback,
            "supports_save_reopen": self.supports_save_reopen,
            "failure_isolation": self.failure_isolation,
            "source_boundary": self.source_boundary,
        }

    def digest(self) -> str:
        return _canonical_hash(self.to_dict())


@dataclass(frozen=True, slots=True, order=True)
class NativeAdapterConformanceIssue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True, slots=True)
class NativeAdapterConformanceReport:
    conformant: bool
    plan_hash: str
    manifest_hash: str
    required_operations: tuple[str, ...]
    required_adapter_keys: tuple[str, ...]
    issues: tuple[NativeAdapterConformanceIssue, ...]
    boundary: str
    schema: str = REPORT_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "conformant": self.conformant,
            "plan_hash": self.plan_hash,
            "manifest_hash": self.manifest_hash,
            "required_operations": list(self.required_operations),
            "required_adapter_keys": list(self.required_adapter_keys),
            "issues": [item.to_dict() for item in self.issues],
            "boundary": self.boundary,
        }

    def digest(self) -> str:
        return _canonical_hash(self.to_dict())

    def assert_conformant(self) -> None:
        if not self.conformant:
            raise ValueError(
                "Native adapter manifest is not conformant: "
                + ", ".join(item.code for item in self.issues)
            )


def _issue(code: str, path: str, message: str) -> NativeAdapterConformanceIssue:
    return NativeAdapterConformanceIssue(code=code, path=path, message=message)


def evaluate_native_adapter_conformance(
    plan: CompilationPlan,
    manifest: NativeAdapterManifest,
) -> NativeAdapterConformanceReport:
    if not isinstance(plan, CompilationPlan):
        raise TypeError("CompilationPlan is required for adapter conformance evaluation")
    if not isinstance(manifest, NativeAdapterManifest):
        raise TypeError("NativeAdapterManifest is required for adapter conformance evaluation")
    normalized = NativeAdapterManifest.from_dict(manifest.to_dict())
    required_operations = tuple(sorted({step.operation for step in plan.steps}))
    required_adapter_keys = tuple(sorted({step.adapter_key for step in plan.steps}))
    issues: list[NativeAdapterConformanceIssue] = []

    identity_checks = (
        ("identity.profile_id", "manifest.profile_id", normalized.profile_id, plan.profile_id),
        (
            "identity.profile_sha256",
            "manifest.profile_sha256",
            normalized.profile_sha256,
            plan.profile_hash,
        ),
        (
            "identity.adapter_contract",
            "manifest.adapter_contract",
            normalized.adapter_contract,
            plan.adapter_contract,
        ),
    )
    for code, path, observed, expected in identity_checks:
        if observed != expected:
            issues.append(_issue(code, path, f"Observed {observed!r}; expected {expected!r}"))

    supported_operations = set(normalized.supported_operations)
    for operation in sorted(set(required_operations) - supported_operations):
        issues.append(
            _issue(
                "operation.missing",
                f"manifest.supported_operations.{operation}",
                f"Adapter manifest does not declare required operation {operation}",
            )
        )
    supported_keys = set(normalized.supported_adapter_keys)
    for adapter_key in sorted(set(required_adapter_keys) - supported_keys):
        issues.append(
            _issue(
                "adapter_key.missing",
                f"manifest.supported_adapter_keys.{adapter_key}",
                f"Adapter manifest does not declare required adapter key {adapter_key}",
            )
        )

    operation_set = set(required_operations)
    if operation_set & _TOPOLOGY_OPERATIONS and not normalized.supports_topology_readback:
        issues.append(
            _issue(
                "readback.topology_missing",
                "manifest.supports_topology_readback",
                "Compilation plan requires native topology readback",
            )
        )
    if operation_set & _LAYOUT_OPERATIONS and not normalized.supports_layout_readback:
        issues.append(
            _issue(
                "readback.layout_missing",
                "manifest.supports_layout_readback",
                "Compilation plan requires native layout readback",
            )
        )
    if operation_set & _SAVE_REOPEN_OPERATIONS and not normalized.supports_save_reopen:
        issues.append(
            _issue(
                "persistence.save_reopen_missing",
                "manifest.supports_save_reopen",
                "Compilation plan requires save, reopen and post-reopen readback",
            )
        )
    if plan.blocked:
        issues.append(
            _issue(
                "plan.blocked",
                "plan.status",
                "A blocked compilation plan cannot be adapter-conformant",
            )
        )

    ordered = tuple(sorted(issues))
    return NativeAdapterConformanceReport(
        conformant=not ordered,
        plan_hash=plan.digest(),
        manifest_hash=normalized.digest(),
        required_operations=required_operations,
        required_adapter_keys=required_adapter_keys,
        issues=ordered,
        boundary=(
            "This report proves only deterministic offline coverage of the compilation plan by "
            "a declared native adapter manifest. Target-runtime behavior, vendor object mapping, "
            "save/reopen fidelity and engineering correctness still require licensed Golden Cases."
        ),
    )
