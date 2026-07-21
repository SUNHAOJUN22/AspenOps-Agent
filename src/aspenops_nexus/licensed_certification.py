from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import tempfile
import uuid
import zipfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeAlias, cast

from . import RUNTIME_SCHEMA, __version__
from .archive_safety import (
    DEFAULT_ARCHIVE_LIMITS,
    ArchiveLimits,
    ArchiveSafetyError,
    read_member_bounded,
    validate_archive,
)
from .batch import dry_run_document
from .certification import (
    PENDING_REAL_ASPEN_CERTIFICATION,
    certify_batch_document,
)
from .compat import compatibility_report
from .config import Settings
from .hashing import canonical_hash, sha256_file

PLAN_SCHEMA = "aspenops.licensed-certification-plan/v1"
PREFLIGHT_SCHEMA = "aspenops.licensed-certification-preflight/v1"
REPORT_SCHEMA = "aspenops.licensed-certification-report/v1"
BUNDLE_SCHEMA = "aspenops.licensed-certification-bundle/v1"
PENDING_ENGINEERING_ACCEPTANCE = "PENDING_ENGINEERING_ACCEPTANCE"
REAL_ASPEN_CERTIFIED = "REAL_ASPEN_CERTIFIED"

KeySource: TypeAlias = str | Path | bytes
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_KEY_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_ALLOWED_BACKENDS = {"aspen_plus", "hysys"}
_ALLOWED_ARCHITECTURES = {"X64", "ARM64"}
_ALLOWED_MEMBERS = {
    "plan.json",
    "preflight.json",
    "report.json",
    "environment.json",
}
_RESERVED_MEMBERS = {"manifest.json", "manifest.sig", "signing-key-id.txt"}


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ValueError(f"Unsupported {label} fields: {', '.join(unknown)}")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must be a non-empty string")
    return normalized


def _finite_nonnegative(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a finite non-negative number")
    number = float(value)
    if not (number >= 0.0 and number < float("inf")):
        raise ValueError(f"{label} must be a finite non-negative number")
    return number


def _positive_integer(value: Any, label: str, *, maximum: int = 1024) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{label} must be between 1 and {maximum}")
    return value


def _digest(value: Any, label: str) -> str:
    text = _text(value, label).lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return text


def _commit(value: Any) -> str:
    text = _text(value, "approved_commit").lower()
    if _COMMIT_RE.fullmatch(text) is None:
        raise ValueError("approved_commit must be a full lowercase 40-character Git SHA")
    return text


def _unique_texts(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    items = tuple(_text(item, f"{label} item") for item in _array(value, label))
    if not items and not allow_empty:
        raise ValueError(f"{label} must contain at least one item")
    normalized = [item.casefold() for item in items]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} must contain unique values")
    return items


def _scoped_texts(value: Any, label: str) -> tuple[str, ...]:
    items = _unique_texts(value, label)
    if any("*" in item or "?" in item for item in items):
        raise ValueError(f"{label} cannot contain wildcard characters")
    return items


def _version_patterns(value: Any) -> tuple[str, ...]:
    patterns = _unique_texts(
        value,
        "runtime_expectation.version_patterns",
        allow_empty=True,
    )
    for pattern in patterns:
        if not pattern.startswith("^") or ".*" in pattern:
            raise ValueError(
                "runtime_expectation.version_patterns must be anchored and cannot contain .*"
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid runtime version pattern {pattern!r}: {exc}") from exc
    return patterns


def _timezone_aware(value: Any, label: str) -> str:
    text = _text(value, label)
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.isoformat()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _pretty_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_key(source: KeySource) -> bytes:
    return source if isinstance(source, bytes) else Path(source).expanduser().read_bytes()


def _load_private_key(source: KeySource) -> Any:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise RuntimeError("Install the 'signing' extra for licensed certification") from exc
    key = serialization.load_pem_private_key(_read_key(source), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Licensed certification requires an Ed25519 private key")
    return key


def _load_public_key(source: KeySource) -> Any:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError("Install the 'signing' extra for licensed certification") from exc
    key = serialization.load_pem_public_key(_read_key(source))
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Licensed certification requires an Ed25519 public key")
    return key


def _public_key_bytes(public_key: Any) -> bytes:
    from cryptography.hazmat.primitives import serialization

    return bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def _key_id(public_key: Any) -> str:
    from cryptography.hazmat.primitives import serialization

    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _sha256_bytes(bytes(raw))[:32]


def _within(path: Path, roots: tuple[Path, ...]) -> bool:
    resolved = path.expanduser().resolve()
    return any(resolved == root or root in resolved.parents for root in roots)


@dataclass(frozen=True, slots=True)
class TolerancePolicy:
    abs_tol: float
    rel_tol: float

    @classmethod
    def from_document(cls, value: Any, label: str) -> TolerancePolicy:
        mapping = _object(value, label)
        _reject_unknown(mapping, {"abs_tol", "rel_tol"}, label)
        if "abs_tol" not in mapping or "rel_tol" not in mapping:
            raise ValueError(f"{label} requires abs_tol and rel_tol")
        return cls(
            abs_tol=_finite_nonnegative(mapping["abs_tol"], f"{label}.abs_tol"),
            rel_tol=_finite_nonnegative(mapping["rel_tol"], f"{label}.rel_tol"),
        )


@dataclass(frozen=True, slots=True)
class RepeatabilityPlan:
    repeats: int
    workers: tuple[int, ...]
    default_tolerance: TolerancePolicy
    output_tolerances: dict[str, TolerancePolicy]

    @classmethod
    def from_document(cls, value: Any) -> RepeatabilityPlan:
        mapping = _object(value, "repeatability")
        _reject_unknown(
            mapping,
            {"repeats", "workers", "default_tolerance", "output_tolerances"},
            "repeatability",
        )
        repeats = _positive_integer(mapping.get("repeats", 3), "repeatability.repeats", maximum=100)
        if repeats < 2:
            raise ValueError("repeatability.repeats must be at least two")
        workers = tuple(
            _positive_integer(item, "repeatability.workers item", maximum=64)
            for item in _array(mapping.get("workers", [1]), "repeatability.workers")
        )
        if not workers or len(workers) != len(set(workers)):
            raise ValueError("repeatability.workers must contain unique worker counts")
        default = TolerancePolicy.from_document(
            mapping.get("default_tolerance"), "repeatability.default_tolerance"
        )
        raw_outputs = _object(
            mapping.get("output_tolerances", {}), "repeatability.output_tolerances"
        )
        output_tolerances: dict[str, TolerancePolicy] = {}
        for raw_key, raw_policy in raw_outputs.items():
            key = _text(raw_key, "repeatability.output_tolerances key")
            output_tolerances[key] = TolerancePolicy.from_document(
                raw_policy, f"repeatability.output_tolerances.{key}"
            )
        return cls(repeats, workers, default, output_tolerances)


@dataclass(frozen=True, slots=True)
class EngineeringAcceptance:
    status: str
    reviewer: str
    approved_at: str
    scope: str

    @classmethod
    def from_document(cls, value: Any) -> EngineeringAcceptance:
        mapping = _object(value, "engineering_acceptance")
        _reject_unknown(
            mapping,
            {"status", "reviewer", "approved_at", "scope"},
            "engineering_acceptance",
        )
        status = _text(mapping.get("status"), "engineering_acceptance.status").lower()
        if status not in {"approved", "pending"}:
            raise ValueError("engineering_acceptance.status must be approved or pending")
        reviewer = _text(mapping.get("reviewer"), "engineering_acceptance.reviewer")
        scope = _text(mapping.get("scope"), "engineering_acceptance.scope")
        approved_at = _timezone_aware(
            mapping.get("approved_at"), "engineering_acceptance.approved_at"
        )
        return cls(status, reviewer, approved_at, scope)


@dataclass(frozen=True, slots=True)
class LicensedCertificationPlan:
    case_id: str
    approved_commit: str
    backend: str
    request: dict[str, Any]
    model_sha256: str
    registry_sha256: str
    repeatability: RepeatabilityPlan
    engineering_acceptance: EngineeringAcceptance
    progids: tuple[str, ...]
    version_patterns: tuple[str, ...]
    license_slots: int
    license_server_identity: str
    feature_names: tuple[str, ...]
    runner_names: tuple[str, ...]
    runner_architecture: str
    signing_required: bool
    signing_key_id: str

    @classmethod
    def from_document(cls, value: Any) -> LicensedCertificationPlan:
        mapping = _object(value, "certification plan")
        _reject_unknown(
            mapping,
            {
                "schema",
                "case_id",
                "approved_commit",
                "backend",
                "request",
                "approved_artifacts",
                "repeatability",
                "engineering_acceptance",
                "runtime_expectation",
                "license_expectation",
                "runner_expectation",
                "signing",
            },
            "certification plan",
        )
        if mapping.get("schema") != PLAN_SCHEMA:
            raise ValueError(f"certification plan schema must be {PLAN_SCHEMA}")
        backend = _text(mapping.get("backend"), "backend").lower()
        if backend not in _ALLOWED_BACKENDS:
            raise ValueError("backend must be aspen_plus or hysys")
        request = _object(mapping.get("request"), "request")
        if _text(request.get("backend", backend), "request.backend").lower() != backend:
            raise ValueError("request.backend must match plan backend")
        request = dict(request)
        request["backend"] = backend
        _text(request.get("model_path"), "request.model_path")
        _text(request.get("registry_path"), "request.registry_path")

        artifacts = _object(mapping.get("approved_artifacts"), "approved_artifacts")
        _reject_unknown(artifacts, {"model_sha256", "registry_sha256"}, "approved_artifacts")
        runtime = _object(mapping.get("runtime_expectation"), "runtime_expectation")
        _reject_unknown(runtime, {"progids", "version_patterns"}, "runtime_expectation")
        license_expectation = _object(mapping.get("license_expectation"), "license_expectation")
        _reject_unknown(
            license_expectation,
            {"slots", "server_identity", "feature_names"},
            "license_expectation",
        )
        runner = _object(mapping.get("runner_expectation"), "runner_expectation")
        _reject_unknown(runner, {"names", "architecture"}, "runner_expectation")
        architecture = _text(runner.get("architecture"), "runner_expectation.architecture").upper()
        if architecture not in _ALLOWED_ARCHITECTURES:
            raise ValueError("runner_expectation.architecture must be X64 or ARM64")
        signing = _object(mapping.get("signing"), "signing")
        _reject_unknown(signing, {"required", "key_id"}, "signing")
        required = signing.get("required")
        if not isinstance(required, bool) or not required:
            raise ValueError("licensed certification requires signing.required=true")
        key_id = _text(signing.get("key_id"), "signing.key_id").lower()
        if _KEY_ID_RE.fullmatch(key_id) is None:
            raise ValueError("signing.key_id must be a 32-character lowercase key identifier")

        repeatability = RepeatabilityPlan.from_document(mapping.get("repeatability"))
        license_slots = _positive_integer(
            license_expectation.get("slots"),
            "license_expectation.slots",
            maximum=64,
        )
        if max(repeatability.workers) > license_slots:
            raise ValueError(
                "repeatability.workers cannot exceed approved license_expectation.slots"
            )

        return cls(
            case_id=_text(mapping.get("case_id"), "case_id"),
            approved_commit=_commit(mapping.get("approved_commit")),
            backend=backend,
            request=request,
            model_sha256=_digest(artifacts.get("model_sha256"), "model_sha256"),
            registry_sha256=_digest(artifacts.get("registry_sha256"), "registry_sha256"),
            repeatability=repeatability,
            engineering_acceptance=EngineeringAcceptance.from_document(
                mapping.get("engineering_acceptance")
            ),
            progids=_scoped_texts(runtime.get("progids"), "runtime_expectation.progids"),
            version_patterns=_version_patterns(runtime.get("version_patterns", [])),
            license_slots=license_slots,
            license_server_identity=_text(
                license_expectation.get("server_identity"),
                "license_expectation.server_identity",
            ),
            feature_names=_scoped_texts(
                license_expectation.get("feature_names"),
                "license_expectation.feature_names",
            ),
            runner_names=_scoped_texts(runner.get("names"), "runner_expectation.names"),
            runner_architecture=architecture,
            signing_required=True,
            signing_key_id=key_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PLAN_SCHEMA,
            "case_id": self.case_id,
            "approved_commit": self.approved_commit,
            "backend": self.backend,
            "request": self.request,
            "approved_artifacts": {
                "model_sha256": self.model_sha256,
                "registry_sha256": self.registry_sha256,
            },
            "repeatability": {
                "repeats": self.repeatability.repeats,
                "workers": list(self.repeatability.workers),
                "default_tolerance": asdict(self.repeatability.default_tolerance),
                "output_tolerances": {
                    key: asdict(policy)
                    for key, policy in self.repeatability.output_tolerances.items()
                },
            },
            "engineering_acceptance": asdict(self.engineering_acceptance),
            "runtime_expectation": {
                "progids": list(self.progids),
                "version_patterns": list(self.version_patterns),
            },
            "license_expectation": {
                "slots": self.license_slots,
                "server_identity": self.license_server_identity,
                "feature_names": list(self.feature_names),
            },
            "runner_expectation": {
                "names": list(self.runner_names),
                "architecture": self.runner_architecture,
            },
            "signing": {"required": True, "key_id": self.signing_key_id},
        }


def load_licensed_plan(path: str | Path) -> LicensedCertificationPlan:
    value = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    return LicensedCertificationPlan.from_document(value)


def _safe_environment(environment: Mapping[str, str]) -> dict[str, Any]:
    keys = (
        "GITHUB_SHA",
        "RUNNER_NAME",
        "RUNNER_ARCH",
        "RUNNER_ENVIRONMENT",
        "ASPENOPS_LICENSE_SERVER_IDENTITY",
        "ASPENOPS_LICENSE_FEATURES",
    )
    return {key: environment.get(key) for key in keys}


def certification_preflight(
    plan: LicensedCertificationPlan,
    settings: Settings,
    *,
    environment: Mapping[str, str] | None = None,
    system_name: str | None = None,
    machine_architecture: str | None = None,
    compatibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if environment is None else environment)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {
        "runtime_schema": RUNTIME_SCHEMA,
        "runtime_version": __version__,
        "plan_sha256": canonical_hash(plan.to_dict()),
        "environment": _safe_environment(env),
    }

    def block(code: str, message: str, **details: Any) -> None:
        blockers.append({"code": code, "message": message, **details})

    def warn(code: str, message: str, **details: Any) -> None:
        warnings.append({"code": code, "message": message, **details})

    actual_system = system_name or platform.system()
    actual_arch = (machine_architecture or env.get("RUNNER_ARCH") or platform.machine()).upper()
    runner_name = env.get("RUNNER_NAME", "")
    evidence["host"] = {
        "system": actual_system,
        "architecture": actual_arch,
        "runner_name": runner_name,
        "runner_environment": env.get("RUNNER_ENVIRONMENT"),
    }
    if actual_system != "Windows":
        block("native_windows_required", "Licensed Aspen certification requires native Windows")
    if env.get("RUNNER_ENVIRONMENT", "").casefold() != "self-hosted":
        block("self_hosted_runner_required", "Runner must identify as self-hosted")
    if runner_name.casefold() not in {name.casefold() for name in plan.runner_names}:
        block("runner_name_not_approved", "Runner name is outside the approved plan scope")
    if actual_arch != plan.runner_architecture:
        block(
            "runner_architecture_mismatch",
            "Runner architecture does not match the approved plan",
            expected=plan.runner_architecture,
            observed=actual_arch,
        )

    observed_commit = (env.get("ASPENOPS_GIT_COMMIT") or env.get("GITHUB_SHA") or "").lower()
    evidence["commit"] = observed_commit or None
    if observed_commit != plan.approved_commit:
        block(
            "commit_mismatch",
            "Checked-out commit is not the approved certification commit",
            expected=plan.approved_commit,
            observed=observed_commit or None,
        )

    if settings.backend != plan.backend:
        block(
            "backend_mismatch",
            "Settings backend does not match the certification plan",
            expected=plan.backend,
            observed=settings.backend,
        )
    if not settings.allowed_roots:
        block("allowed_roots_missing", "ASPENOPS_ALLOWED_ROOTS must be explicitly configured")

    model_path = Path(str(plan.request["model_path"])).expanduser().resolve()
    registry_path = Path(str(plan.request["registry_path"])).expanduser().resolve()
    approved_roots = tuple(root.expanduser().resolve() for root in settings.allowed_roots)
    evidence["artifacts"] = {
        "model_path": str(model_path),
        "registry_path": str(registry_path),
    }
    for label, path, expected_digest in (
        ("model", model_path, plan.model_sha256),
        ("registry", registry_path, plan.registry_sha256),
    ):
        if not path.is_file():
            block(f"{label}_missing", f"Approved {label} file does not exist")
            continue
        if not _within(path, approved_roots):
            block(f"{label}_outside_allowed_roots", f"Approved {label} is outside allowed roots")
        observed_digest = sha256_file(path)
        cast(dict[str, Any], evidence["artifacts"])[f"{label}_sha256"] = observed_digest
        if observed_digest != expected_digest:
            block(
                f"{label}_digest_mismatch",
                f"Approved {label} digest does not match",
                expected=expected_digest,
                observed=observed_digest,
            )

    if plan.engineering_acceptance.status != "approved":
        block(
            "engineering_acceptance_pending",
            "Engineering acceptance is not approved for this exact plan",
        )
    evidence["engineering_acceptance"] = asdict(plan.engineering_acceptance)

    if settings.license_slots != plan.license_slots:
        block(
            "license_slot_mismatch",
            "Configured license slots do not match the approved plan",
            expected=plan.license_slots,
            observed=settings.license_slots,
        )
    server_identity = env.get("ASPENOPS_LICENSE_SERVER_IDENTITY", "")
    if server_identity != plan.license_server_identity:
        block("license_server_mismatch", "License server identity does not match the plan")
    observed_features = {
        item.strip().casefold()
        for item in env.get("ASPENOPS_LICENSE_FEATURES", "").split(";")
        if item.strip()
    }
    expected_features = {item.casefold() for item in plan.feature_names}
    if not expected_features.issubset(observed_features):
        block(
            "license_features_missing",
            "Required license features were not declared by the runner",
            missing=sorted(expected_features - observed_features),
        )

    report = compatibility_report() if compatibility is None else compatibility
    candidates = report.get(plan.backend, [])
    observed_progids = {
        str(item.get("progid", "")).casefold()
        for item in candidates
        if isinstance(item, dict) and str(item.get("registry_view", "")).casefold() != "fallback"
    }
    approved_progids = {item.casefold() for item in plan.progids}
    evidence["registered_progids"] = sorted(observed_progids)
    if not observed_progids.intersection(approved_progids):
        block("approved_progid_missing", "No approved COM ProgID is registered on the runner")
    if plan.version_patterns:
        warn(
            "runtime_version_verified_after_open",
            "Version patterns are checked against the opened simulator runtime, not registry names",
            patterns=list(plan.version_patterns),
        )

    key_path_text = env.get("ASPENOPS_CERT_SIGNING_KEY", "").strip()
    if not key_path_text:
        block("signing_key_missing", "ASPENOPS_CERT_SIGNING_KEY must identify a mounted key file")
    else:
        key_path = Path(key_path_text).expanduser().resolve()
        workspace_text = env.get("GITHUB_WORKSPACE", "").strip()
        workspace = Path(workspace_text).expanduser().resolve() if workspace_text else None
        if not key_path.is_file():
            block("signing_key_unreadable", "Mounted signing key file is unavailable")
        elif workspace is not None and (key_path == workspace or workspace in key_path.parents):
            block(
                "signing_key_inside_workspace",
                "Signing key must be outside the repository workspace",
            )
        else:
            try:
                observed_key_id = _key_id(_load_private_key(key_path).public_key())
                evidence["signing_key_id"] = observed_key_id
                if observed_key_id != plan.signing_key_id:
                    block(
                        "signing_key_id_mismatch",
                        "Mounted signing key does not match the approved key identifier",
                        expected=plan.signing_key_id,
                        observed=observed_key_id,
                    )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                block("signing_key_invalid", f"Signing key validation failed: {type(exc).__name__}")

    try:
        settings.state_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.state_dir, prefix="preflight-", delete=True):
            pass
    except OSError as exc:
        block("state_dir_not_writable", f"State directory is not writable: {type(exc).__name__}")

    if not any(item["code"] in {"model_missing", "registry_missing"} for item in blockers):
        try:
            evidence["dry_run"] = dry_run_document(plan.request, settings)
        except Exception as exc:
            block(
                "dry_run_failed",
                f"Certification request dry-run failed: {type(exc).__name__}: {exc}",
            )

    ready = not blockers
    return {
        "schema": PREFLIGHT_SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "ready": ready,
        "runtime_execution_allowed": ready,
        "certification_status": PENDING_REAL_ASPEN_CERTIFICATION,
        "blockers": blockers,
        "warnings": warnings,
        "evidence": evidence,
        "boundary": (
            "Preflight readiness authorizes only execution of the scoped licensed test plan. "
            "It does not grant REAL_ASPEN_CERTIFIED and does not constitute engineering approval."
        ),
    }


def _sanitized_runtime_environment(environment: Mapping[str, str]) -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "runner_name": environment.get("RUNNER_NAME"),
        "runner_arch": environment.get("RUNNER_ARCH"),
        "runner_environment": environment.get("RUNNER_ENVIRONMENT"),
        "git_commit": environment.get("ASPENOPS_GIT_COMMIT") or environment.get("GITHUB_SHA"),
        "license_server_identity": environment.get("ASPENOPS_LICENSE_SERVER_IDENTITY"),
        "license_features": [
            item.strip()
            for item in environment.get("ASPENOPS_LICENSE_FEATURES", "").split(";")
            if item.strip()
        ],
    }


def write_licensed_certification_bundle(
    *,
    plan: LicensedCertificationPlan,
    preflight: dict[str, Any],
    report: dict[str, Any],
    environment: Mapping[str, str],
    output_path: str | Path,
    signing_private_key: KeySource,
) -> tuple[Path, bytes]:
    private_key = _load_private_key(signing_private_key)
    public_key = private_key.public_key()
    key_id = _key_id(public_key)
    if key_id != plan.signing_key_id:
        raise ValueError("Signing key identifier does not match the certification plan")
    members = {
        "plan.json": _pretty_bytes(plan.to_dict()),
        "preflight.json": _pretty_bytes(preflight),
        "report.json": _pretty_bytes(report),
        "environment.json": _pretty_bytes(_sanitized_runtime_environment(environment)),
    }
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "runtime_schema": RUNTIME_SCHEMA,
        "runtime_version": __version__,
        "certification_status": PENDING_REAL_ASPEN_CERTIFICATION,
        "case_id": plan.case_id,
        "approved_commit": plan.approved_commit,
        "plan_sha256": canonical_hash(plan.to_dict()),
        "members": {
            name: {"sha256": _sha256_bytes(payload), "size": len(payload)}
            for name, payload in members.items()
        },
        "signing": {"status": "signed", "algorithm": "Ed25519", "key_id": key_id},
        "boundary": (
            "A valid signature proves bundle origin and integrity for the scoped run. "
            "It does not by itself grant REAL_ASPEN_CERTIFIED."
        ),
    }
    signature = base64.b64encode(private_key.sign(_canonical_bytes(manifest)))
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr("manifest.json", _pretty_bytes(manifest))
            for name, payload in members.items():
                archive.writestr(name, payload)
            archive.writestr("manifest.sig", signature)
            archive.writestr("signing-key-id.txt", key_id.encode("ascii"))
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output, _public_key_bytes(public_key)


def verify_licensed_certification_bundle(
    bundle_path: str | Path,
    *,
    trusted_public_key: KeySource,
    limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS,
) -> dict[str, Any]:
    bundle = Path(bundle_path).expanduser().resolve()
    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            infos = validate_archive(bundle, archive, limits)
            expected = _ALLOWED_MEMBERS | _RESERVED_MEMBERS
            actual = set(infos)
            if actual != expected:
                return {
                    "ok": False,
                    "verification_status": "structure-invalid",
                    "missing": sorted(expected - actual),
                    "unexpected": sorted(actual - expected),
                }
            manifest_payload = read_member_bounded(archive, infos["manifest.json"], limits)
            manifest_value = json.loads(manifest_payload)
            if (
                not isinstance(manifest_value, dict)
                or manifest_value.get("schema") != BUNDLE_SCHEMA
            ):
                return {"ok": False, "verification_status": "structure-invalid"}
            manifest = cast(dict[str, Any], manifest_value)
            declarations = _object(manifest.get("members"), "manifest.members")
            member_checks: dict[str, bool] = {}
            for name in _ALLOWED_MEMBERS:
                declaration = _object(declarations.get(name), f"manifest.members.{name}")
                payload = read_member_bounded(archive, infos[name], limits)
                member_checks[name] = declaration.get("sha256") == _sha256_bytes(
                    payload
                ) and declaration.get("size") == len(payload)
            signing = _object(manifest.get("signing"), "manifest.signing")
            key_id = _text(signing.get("key_id"), "manifest.signing.key_id")
            if signing.get("status") != "signed" or signing.get("algorithm") != "Ed25519":
                return {"ok": False, "verification_status": "structure-invalid"}
            public_key = _load_public_key(trusted_public_key)
            if _key_id(public_key) != key_id:
                return {"ok": False, "verification_status": "signed-invalid"}
            encoded_signature = read_member_bounded(archive, infos["manifest.sig"], limits)
            try:
                signature = base64.b64decode(encoded_signature, validate=True)
                public_key.verify(signature, _canonical_bytes(manifest))
            except Exception:
                return {
                    "ok": False,
                    "verification_status": "signed-invalid",
                    "member_checks": member_checks,
                }
            content_valid = all(member_checks.values())
            return {
                "ok": content_valid,
                "verification_status": "signed-valid" if content_valid else "content-invalid",
                "member_checks": member_checks,
                "manifest": manifest,
            }
    except (OSError, ValueError, zipfile.BadZipFile, ArchiveSafetyError) as exc:
        return {
            "ok": False,
            "verification_status": "structure-invalid",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _runtime_scope_evidence(
    plan: LicensedCertificationPlan,
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    approved_progids = {item.casefold() for item in plan.progids}
    compiled_patterns = [re.compile(pattern) for pattern in plan.version_patterns]
    identities: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    for report_index, report in enumerate(reports):
        runs = report.get("runs", [])
        if not isinstance(runs, list):
            violations.append({"report": report_index, "code": "runtime_runs_missing"})
            continue
        for repeat_index, run in enumerate(runs):
            if not isinstance(run, list):
                violations.append(
                    {
                        "report": report_index,
                        "repeat": repeat_index,
                        "code": "runtime_run_malformed",
                    }
                )
                continue
            for point_index, result in enumerate(run):
                if not isinstance(result, dict):
                    violations.append(
                        {
                            "report": report_index,
                            "repeat": repeat_index,
                            "point": point_index,
                            "code": "runtime_result_malformed",
                        }
                    )
                    continue
                diagnostics = result.get("diagnostics", {})
                runtime = diagnostics.get("runtime") if isinstance(diagnostics, dict) else None
                if not isinstance(runtime, dict):
                    violations.append(
                        {
                            "report": report_index,
                            "repeat": repeat_index,
                            "point": point_index,
                            "code": "runtime_identity_missing",
                        }
                    )
                    continue
                progid = str(runtime.get("progid") or "")
                exposed = runtime.get("exposed", {})
                exposed_values = (
                    [str(value) for value in exposed.values()] if isinstance(exposed, dict) else []
                )
                identity = {
                    "report": report_index,
                    "repeat": repeat_index,
                    "point": point_index,
                    "progid": progid,
                    "exposed": exposed_values,
                }
                identities.append(identity)
                if progid.casefold() not in approved_progids:
                    violations.append({**identity, "code": "runtime_progid_out_of_scope"})
                if compiled_patterns and not any(
                    pattern.search(value)
                    for pattern in compiled_patterns
                    for value in exposed_values
                ):
                    violations.append({**identity, "code": "runtime_version_out_of_scope"})
    if not identities:
        violations.append({"code": "no_runtime_identity_evidence"})
    return {
        "passed": not violations,
        "identities": identities,
        "violations": violations,
        "approved_progids": list(plan.progids),
        "approved_version_patterns": list(plan.version_patterns),
    }


def execute_licensed_certification(
    plan: LicensedCertificationPlan,
    settings: Settings,
    *,
    output_dir: str | Path,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if environment is None else environment)
    output = Path(output_dir).expanduser().resolve()
    approved_output_roots = (settings.state_dir.resolve(), *settings.allowed_roots)
    if not _within(output, approved_output_roots):
        raise PermissionError(
            "Licensed certification output must be inside state_dir or allowed roots"
        )
    output.mkdir(parents=True, exist_ok=True)
    preflight = certification_preflight(plan, settings, environment=env)
    preflight_path = output / "preflight.json"
    preflight_path.write_bytes(_pretty_bytes(preflight))
    if not preflight["ready"]:
        return {
            "schema": REPORT_SCHEMA,
            "executed": False,
            "passed": False,
            "certification_status": PENDING_REAL_ASPEN_CERTIFICATION,
            "preflight_path": str(preflight_path),
            "blockers": preflight["blockers"],
        }

    reports: list[dict[str, Any]] = []
    output_tolerances = {
        key: asdict(policy) for key, policy in plan.repeatability.output_tolerances.items()
    }
    for workers in plan.repeatability.workers:
        try:
            repeatability_report = certify_batch_document(
                plan.request,
                settings,
                repeats=plan.repeatability.repeats,
                workers=workers,
                abs_tol=plan.repeatability.default_tolerance.abs_tol,
                rel_tol=plan.repeatability.default_tolerance.rel_tol,
                output_tolerances=output_tolerances,
                engineering_approved=True,
            )
        except Exception as exc:
            repeatability_report = {
                "passed": False,
                "repeatability_gate_passed": False,
                "workers": workers,
                "error": f"{type(exc).__name__}: {exc}",
                "certification_status": PENDING_REAL_ASPEN_CERTIFICATION,
            }
        reports.append(repeatability_report)

    repeatability_gate_passed = all(bool(item.get("repeatability_gate_passed")) for item in reports)
    runtime_scope = _runtime_scope_evidence(plan, reports)
    runtime_gate_passed = repeatability_gate_passed and bool(runtime_scope["passed"])
    report = {
        "schema": REPORT_SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "case_id": plan.case_id,
        "approved_commit": plan.approved_commit,
        "backend": plan.backend,
        "executed": True,
        "repeatability_gate_passed": repeatability_gate_passed,
        "runtime_scope": runtime_scope,
        "runtime_gate_passed": runtime_gate_passed,
        "passed": runtime_gate_passed,
        "certification_status": PENDING_REAL_ASPEN_CERTIFICATION,
        "engineering_acceptance": asdict(plan.engineering_acceptance),
        "repeatability_reports": reports,
        "remaining_manual_gates": [
            "external process protection review",
            "licensed failure-injection matrix review",
            "physical and balance acceptance",
            "real performance report review",
            "trusted-signature verification and human approval",
        ],
        "boundary": (
            "Successful execution completes the scoped runtime repeatability gate only. "
            "AspenOps never transitions itself to REAL_ASPEN_CERTIFIED."
        ),
    }
    report_path = output / "licensed-certification-report.json"
    report_path.write_bytes(_pretty_bytes(report))
    key_path = env["ASPENOPS_CERT_SIGNING_KEY"]
    bundle_path, public_key = write_licensed_certification_bundle(
        plan=plan,
        preflight=preflight,
        report=report,
        environment=env,
        output_path=output / "licensed-certification-bundle.zip",
        signing_private_key=key_path,
    )
    verification = verify_licensed_certification_bundle(bundle_path, trusted_public_key=public_key)
    return {
        **report,
        "report_path": str(report_path),
        "preflight_path": str(preflight_path),
        "bundle_path": str(bundle_path),
        "bundle_verification": verification,
    }
