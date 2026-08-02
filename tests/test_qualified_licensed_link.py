from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.licensed_certification import LicensedCertificationPlan
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.qualified_compilation import (
    RuntimeQualifiedCompilationPlan,
    qualify_compilation_plan,
)
from aspenops_nexus.qualified_licensed_link import (
    OFFLINE_BINDING_ONLY,
    QualifiedLicensedCertificationLink,
    link_qualified_compilation_to_licensed_plan,
)
from aspenops_nexus.runtime_qualification import (
    GoldenCaseQualification,
    RuntimeQualificationStatement,
    sign_runtime_qualification,
    verify_runtime_qualification,
)
from aspenops_nexus.simulator_capabilities import (
    SimulatorCapabilityProfile,
    get_builtin_capability_profile,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "examples/process-design-v2.example.json"
CASE_ID = "qualification-case-001"
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def design() -> ProcessDesignIR:
    value = json.loads(DESIGN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return ProcessDesignIR.from_dict(value)


def qualification_for(
    profile: SimulatorCapabilityProfile,
    *,
    case_ids: tuple[str, ...] = (CASE_ID,),
) -> Any:
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
        approval_scope="Synthetic Phase 4 link contract",
        golden_cases=tuple(
            GoldenCaseQualification(
                case_id=case_id,
                evidence_bundle_sha256="c" * 64,
                topology_sha256="d" * 64,
                layout_sha256="e" * 64,
                passed=True,
            )
            for case_id in case_ids
        ),
    )
    return verify_runtime_qualification(
        sign_runtime_qualification(statement, private_pem),
        trusted_public_key=public_pem,
        now=NOW,
        required_case_ids=case_ids,
    )


def licensed_plan(
    *, case_id: str = CASE_ID, backend: str = "aspen_plus"
) -> LicensedCertificationPlan:
    return LicensedCertificationPlan.from_document(
        {
            "schema": "aspenops.licensed-certification-plan/v1",
            "case_id": case_id,
            "approved_commit": "1" * 40,
            "backend": backend,
            "request": {
                "backend": backend,
                "model_path": "C:/approved/case.bkp",
                "registry_path": "C:/approved/registry.json",
                "reads": [{"key": "product.purity"}],
                "points": [{}],
                "workers": 1,
            },
            "approved_artifacts": {
                "model_sha256": "2" * 64,
                "registry_sha256": "3" * 64,
            },
            "repeatability": {
                "repeats": 3,
                "workers": [1],
                "default_tolerance": {"abs_tol": 1e-6, "rel_tol": 1e-6},
                "output_tolerances": {"product.purity": {"abs_tol": 1e-5, "rel_tol": 1e-5}},
            },
            "engineering_acceptance": {
                "status": "approved",
                "reviewer": "qualified-engineer",
                "approved_at": "2026-08-02T00:00:00+00:00",
                "scope": "Synthetic generated-case certification link",
            },
            "runtime_expectation": {
                "progids": ["Apwn.Document.40.0"],
                "version_patterns": ["^40\\."],
            },
            "license_expectation": {
                "slots": 1,
                "server_identity": "approved-license-server",
                "feature_names": ["ASPEN_PLUS"],
            },
            "runner_expectation": {
                "names": ["aspen-cert-runner-01"],
                "architecture": "X64",
            },
            "signing": {"required": True, "key_id": "4" * 32},
        }
    )


def qualified_plan(
    profile: SimulatorCapabilityProfile,
    *,
    case_ids: tuple[str, ...] = (CASE_ID,),
) -> RuntimeQualifiedCompilationPlan:
    return qualify_compilation_plan(
        design(),
        profile,
        qualification_for(profile, case_ids=case_ids),
        required_case_ids=case_ids,
    )


def valid_inputs() -> tuple[
    LicensedCertificationPlan,
    RuntimeQualifiedCompilationPlan,
    SimulatorCapabilityProfile,
]:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    return licensed_plan(), qualified_plan(profile), profile


def test_link_is_deterministic_strict_and_round_trips() -> None:
    licensed, qualified, profile = valid_inputs()
    first = link_qualified_compilation_to_licensed_plan(licensed, qualified, profile)
    second = link_qualified_compilation_to_licensed_plan(licensed, qualified, profile)

    assert first == second
    assert first.digest() == second.digest()
    assert first.execution_status == OFFLINE_BINDING_ONLY
    assert first.real_aspen_status == "PENDING_REAL_ASPEN_CERTIFICATION"
    assert first.case_id == CASE_ID
    assert first.golden_case_ids == (CASE_ID,)
    assert QualifiedLicensedCertificationLink.from_dict(first.to_dict()) == first
    first.assert_matches(licensed, qualified, profile)


def test_link_binds_all_load_bearing_hashes() -> None:
    licensed, qualified, profile = valid_inputs()
    link = link_qualified_compilation_to_licensed_plan(licensed, qualified, profile)

    assert link.model_sha256 == licensed.model_sha256
    assert link.registry_sha256 == licensed.registry_sha256
    assert link.approved_commit == licensed.approved_commit
    assert link.qualified_plan_sha256 == qualified.digest()
    assert link.base_plan_sha256 == qualified.base_plan.digest()
    assert link.qualification_evidence_sha256 == qualified.qualification_evidence_sha256
    assert link.profile_sha256 == profile.digest()
    assert link.adapter_code_sha256 == qualified.adapter_code_sha256
    assert link.runtime_identity_sha256 == qualified.runtime_identity_sha256
    assert link.expected_topology_sha256 == qualified.expected_topology.digest()
    assert link.expected_layout_sha256 == qualified.expected_layout_hash


def test_backend_and_profile_substitution_fail_closed() -> None:
    licensed, qualified, profile = valid_inputs()
    with pytest.raises(ValueError, match="backend"):
        link_qualified_compilation_to_licensed_plan(
            replace(licensed, backend="hysys"),
            qualified,
            profile,
        )

    forged_profile = replace(profile, adapter_contract="forged-contract")
    with pytest.raises(ValueError, match="qualification|profile"):
        link_qualified_compilation_to_licensed_plan(
            licensed,
            qualified,
            forged_profile,
        )


def test_missing_licensed_case_in_golden_cases_fails_closed() -> None:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    qualified = qualified_plan(profile, case_ids=("different-case",))
    with pytest.raises(ValueError, match="Golden Case|required"):
        link_qualified_compilation_to_licensed_plan(
            licensed_plan(),
            qualified,
            profile,
        )


def test_additional_required_case_must_be_qualified() -> None:
    licensed, qualified, profile = valid_inputs()
    with pytest.raises(ValueError, match="required Golden Cases"):
        link_qualified_compilation_to_licensed_plan(
            licensed,
            qualified,
            profile,
            required_case_ids=("second-case",),
        )


def test_link_detects_current_input_drift() -> None:
    licensed, qualified, profile = valid_inputs()
    link = link_qualified_compilation_to_licensed_plan(licensed, qualified, profile)

    with pytest.raises(ValueError, match="licensed_plan_sha256|model_sha256"):
        link.assert_matches(
            replace(licensed, model_sha256="9" * 64),
            qualified,
            profile,
        )
    with pytest.raises(ValueError, match="approved_commit|licensed_plan_sha256"):
        link.assert_matches(
            replace(licensed, approved_commit="8" * 40),
            qualified,
            profile,
        )


def test_serialized_link_rejects_tampering_and_unknown_fields() -> None:
    licensed, qualified, profile = valid_inputs()
    document = link_qualified_compilation_to_licensed_plan(
        licensed,
        qualified,
        profile,
    ).to_dict()

    forged = dict(document)
    forged["execution_status"] = "EXECUTABLE"
    with pytest.raises(ValueError, match="cannot authorize"):
        QualifiedLicensedCertificationLink.from_dict(forged)

    forged = dict(document)
    forged["model_sha256"] = "bad"
    with pytest.raises(ValueError, match="SHA-256"):
        QualifiedLicensedCertificationLink.from_dict(forged)

    forged = dict(document)
    forged["unexpected"] = True
    with pytest.raises(ValueError, match="exactly"):
        QualifiedLicensedCertificationLink.from_dict(forged)


def test_link_case_order_is_canonical() -> None:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    cases = (CASE_ID, "second-case")
    qualified = qualified_plan(profile, case_ids=cases)
    link = link_qualified_compilation_to_licensed_plan(
        licensed_plan(),
        qualified,
        profile,
        required_case_ids=("second-case", CASE_ID),
    )
    assert link.golden_case_ids == tuple(sorted(cases))
