from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.compilation_plan import compile_process_design
from aspenops_nexus.native_builder import NativeBuildError, execute_compilation_plan
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.qualified_compilation import (
    QUALIFIED_PLAN_SCHEMA,
    RuntimeQualifiedCompilationPlan,
    qualify_compilation_plan,
)
from aspenops_nexus.runtime_qualification import (
    GoldenCaseQualification,
    RuntimeQualificationStatement,
    VerifiedRuntimeQualification,
    sign_runtime_qualification,
    verify_runtime_qualification,
)
from aspenops_nexus.simulator_capabilities import (
    SimulatorCapabilityProfile,
    get_builtin_capability_profile,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "examples/process-design-v2.example.json"
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def design() -> ProcessDesignIR:
    value = json.loads(DESIGN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return ProcessDesignIR.from_dict(value)


def proof_for(
    profile: SimulatorCapabilityProfile,
    *,
    cases: tuple[str, ...] = ("HEATER_FLASH_V15",),
) -> VerifiedRuntimeQualification:
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    statement = RuntimeQualificationStatement(
        profile_id=profile.profile_id,
        profile_sha256=profile.digest(),
        simulator=profile.simulator,
        marketing_version=profile.marketing_version,
        adapter_contract=profile.adapter_contract,
        adapter_code_sha256="a" * 64,
        runtime_identity_sha256="b" * 64,
        issued_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=1),
        approved_by="Engineer A",
        approval_scope="Synthetic qualification contract test",
        golden_cases=tuple(
            GoldenCaseQualification(
                case_id=case_id,
                evidence_bundle_sha256="c" * 64,
                topology_sha256="d" * 64,
                layout_sha256="e" * 64,
                passed=True,
            )
            for case_id in cases
        ),
    )
    return verify_runtime_qualification(
        sign_runtime_qualification(statement, private_pem),
        trusted_public_key=public_pem,
        now=NOW,
    )


def test_offline_profile_can_only_execute_through_verified_wrapper() -> None:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    base = compile_process_design(design(), profile)
    assert base.status == "PLAN_ONLY"
    qualified = qualify_compilation_plan(
        design(),
        profile,
        proof_for(profile),
        required_case_ids=("HEATER_FLASH_V15",),
    )
    assert qualified.schema == QUALIFIED_PLAN_SCHEMA
    assert qualified.base_plan.status == "PLAN_ONLY"
    assert qualified.executable is True
    qualified.assert_executable()
    assert qualified.profile_id == profile.profile_id
    assert qualified.profile_hash == profile.digest()
    assert qualified.adapter_code_sha256 == "a" * 64
    assert qualified.runtime_identity_sha256 == "b" * 64
    assert len(qualified.qualification_evidence_sha256) == 64
    assert len(qualified.qualification_key_id) == 32


def test_enum_only_verified_profile_does_not_authorize_native_execution() -> None:
    profile = replace(
        get_builtin_capability_profile("aspen_plus", "15"),
        qualification="VERIFIED_ON_TARGET_RUNTIME",
    )
    base = compile_process_design(design(), profile)
    assert base.status == "EXECUTABLE"
    with pytest.raises(NativeBuildError, match="RuntimeQualifiedCompilationPlan"):
        execute_compilation_plan(base, object())  # type: ignore[arg-type]


def test_qualified_plan_serialization_and_digest_are_deterministic() -> None:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    proof = proof_for(profile, cases=("B_CASE", "A_CASE"))
    first = qualify_compilation_plan(
        design(),
        profile,
        proof,
        required_case_ids=("B_CASE", "A_CASE", "A_CASE"),
    )
    second = RuntimeQualifiedCompilationPlan(
        base_plan=first.base_plan,
        qualification=first.qualification,
        required_case_ids=("A_CASE", "B_CASE"),
    )
    assert first.required_case_ids == ("A_CASE", "B_CASE")
    assert first.to_dict() == second.to_dict()
    assert first.digest() == second.digest()
    payload = first.to_dict()
    assert payload["base_plan_sha256"] == first.base_plan.digest()
    assert "does not replace native readback" in payload["boundary"]


def test_profile_or_proof_mismatch_fails_closed() -> None:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    proof = proof_for(profile)
    mismatches = (
        replace(profile, profile_id="wrong"),
        replace(profile, marketing_version="14"),
        replace(profile, adapter_contract="wrong"),
        get_builtin_capability_profile("hysys", "15"),
    )
    for changed in mismatches:
        with pytest.raises(ValueError):
            qualify_compilation_plan(design(), changed, proof)


def test_required_golden_case_and_revoked_profile_fail_closed() -> None:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    proof = proof_for(profile)
    with pytest.raises(ValueError, match="missing required Golden Cases"):
        qualify_compilation_plan(
            design(),
            profile,
            proof,
            required_case_ids=("MISSING",),
        )
    revoked = replace(profile, qualification="REVOKED")
    revoked_proof = proof_for(revoked)
    with pytest.raises(ValueError, match="Revoked"):
        qualify_compilation_plan(design(), revoked, revoked_proof)


def test_blocked_base_plan_cannot_be_runtime_qualified() -> None:
    value: dict[str, Any] = json.loads(DESIGN.read_text(encoding="utf-8"))
    value["streams"][0]["target"] = {"equipment_id": "MISSING", "port_id": "IN"}
    blocked_design = ProcessDesignIR.from_dict(value)
    profile = get_builtin_capability_profile("aspen_plus", "15")
    with pytest.raises(ValueError, match="blocked compilation plan"):
        qualify_compilation_plan(blocked_design, profile, proof_for(profile))
