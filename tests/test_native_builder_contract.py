from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.compilation_plan import CompilationStep, compile_process_design
from aspenops_nexus.native_builder import (
    NativeBuildError,
    _contains_expected,
    execute_compilation_plan,
)
from aspenops_nexus.native_topology import NativeTopologySnapshot, TopologyNode
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.qualified_compilation import (
    RuntimeQualifiedCompilationPlan,
    qualify_compilation_plan,
)
from aspenops_nexus.runtime_execution_authorization import RuntimeRevocationPolicy
from aspenops_nexus.runtime_qualification import (
    GoldenCaseQualification,
    RuntimeQualificationStatement,
    sign_runtime_qualification,
    verify_runtime_qualification,
)
from aspenops_nexus.signed_revocation_policy import (
    REVOCATION_AUTHORITY_DIRECTORY,
    REVOCATION_CHECKPOINT_FILENAME,
    SIGNED_POLICY_FILENAME,
    SignedRevocationPolicyStatement,
    advance_revocation_policy_checkpoint,
    sign_revocation_policy,
    verify_revocation_policy,
)
from aspenops_nexus.simulator_capabilities import (
    SimulatorCapabilityProfile,
    get_builtin_capability_profile,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "examples/process-design-v2.example.json"
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
CASE_ID = "HEATER_FLASH_V15"


def design() -> ProcessDesignIR:
    value = json.loads(DESIGN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return ProcessDesignIR.from_dict(value)


def authorization_context(
    tmp_path: Path,
) -> tuple[
    RuntimeQualifiedCompilationPlan,
    SimulatorCapabilityProfile,
    dict[str, Any],
]:
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    profile = get_builtin_capability_profile("aspen_plus", "15")
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
        approval_scope="Synthetic native-builder contract test",
        golden_cases=(
            GoldenCaseQualification(
                case_id=CASE_ID,
                evidence_bundle_sha256="c" * 64,
                topology_sha256="d" * 64,
                layout_sha256="e" * 64,
                passed=True,
            ),
        ),
    )
    envelope = sign_runtime_qualification(statement, private_pem)
    signing = envelope["signing"]
    assert isinstance(signing, dict)
    key_id = signing["key_id"]
    assert isinstance(key_id, str)
    (tmp_path / f"{key_id}.pem").write_bytes(public_pem)

    authority_private = Ed25519PrivateKey.generate()
    authority_private_pem = authority_private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    authority_public_pem = authority_private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    policy = RuntimeRevocationPolicy(
        policy_id="test-policy",
        issued_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=1),
        revoked_signing_key_ids=(),
        revoked_qualification_evidence_sha256=(),
        revoked_profile_ids=(),
        revoked_profile_sha256=(),
        revoked_adapter_code_sha256=(),
        revoked_runtime_identity_sha256=(),
    )
    policy_envelope = sign_revocation_policy(
        SignedRevocationPolicyStatement(
            sequence=1,
            previous_policy_sha256=None,
            policy=policy,
        ),
        authority_private_pem,
    )
    verified_policy = verify_revocation_policy(
        policy_envelope,
        trusted_public_key=authority_public_pem,
        now=NOW,
    )
    policy_signing = policy_envelope["signing"]
    assert isinstance(policy_signing, dict)
    authority_key_id = policy_signing["key_id"]
    assert isinstance(authority_key_id, str)
    authority_dir = tmp_path / REVOCATION_AUTHORITY_DIRECTORY
    authority_dir.mkdir(parents=True, exist_ok=True)
    (authority_dir / f"{authority_key_id}.pem").write_bytes(authority_public_pem)
    (tmp_path / SIGNED_POLICY_FILENAME).write_text(
        json.dumps(policy_envelope, sort_keys=True),
        encoding="utf-8",
    )
    (tmp_path / REVOCATION_CHECKPOINT_FILENAME).write_text(
        json.dumps(
            advance_revocation_policy_checkpoint(verified_policy).to_dict(),
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    verified = verify_runtime_qualification(
        envelope,
        trusted_public_key=public_pem,
        now=NOW,
        required_case_ids=(CASE_ID,),
    )
    plan = qualify_compilation_plan(
        design(),
        profile,
        verified,
        required_case_ids=(CASE_ID,),
    )
    return plan, profile, envelope


class FakeAdapter:
    def __init__(
        self,
        plan: RuntimeQualifiedCompilationPlan,
        *,
        topology: NativeTopologySnapshot | None = None,
        layout_hash: str | None = None,
    ) -> None:
        self._profile_id = plan.profile_id
        self._profile_hash = plan.profile_hash
        self._adapter_code_sha256 = plan.adapter_code_sha256
        self._runtime_identity_sha256 = plan.runtime_identity_sha256
        self.topology = topology or plan.expected_topology
        self.layout_hash = layout_hash or plan.expected_layout_hash
        self.operations: list[str] = []
        self.override_results: dict[str, Any] = {}

    @property
    def profile_id(self) -> str:
        return self._profile_id

    @property
    def profile_hash(self) -> str:
        return self._profile_hash

    @property
    def adapter_code_sha256(self) -> str:
        return self._adapter_code_sha256

    @property
    def runtime_identity_sha256(self) -> str:
        return self._runtime_identity_sha256

    def apply_step(self, step: CompilationStep) -> dict[str, Any]:
        self.operations.append(step.operation)
        override = self.override_results.get(step.step_id)
        if override is not None:
            return override
        return dict(step.expected_readback)

    def read_topology(self) -> NativeTopologySnapshot:
        self.operations.append("read_topology")
        return self.topology

    def read_layout_hash(self) -> str:
        self.operations.append("read_layout_hash")
        return self.layout_hash


def execute(
    plan: RuntimeQualifiedCompilationPlan,
    adapter: FakeAdapter,
    profile: SimulatorCapabilityProfile,
    envelope: dict[str, Any],
    trusted_key_dir: Path,
):
    return execute_compilation_plan(
        plan,
        adapter,
        profile=profile,
        qualification_source=envelope,
        trusted_key_dir=trusted_key_dir,
        now=NOW,
    )


def test_execute_compilation_plan_success(tmp_path: Path) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    adapter = FakeAdapter(plan)
    record = execute(plan, adapter, profile, envelope, tmp_path)
    assert record.completed is True
    assert record.plan_hash == plan.digest()
    assert record.profile_id == plan.profile_id
    assert record.profile_hash == plan.profile_hash
    assert record.qualification_evidence_sha256 == plan.qualification_evidence_sha256
    assert record.adapter_code_sha256 == plan.adapter_code_sha256
    assert record.runtime_identity_sha256 == plan.runtime_identity_sha256
    assert len(record.runtime_authorization_sha256) == 64
    assert len(record.revocation_policy_sha256) == 64
    assert len(record.revocation_policy_signing_key_id) == 32
    assert record.revocation_policy_sequence == 1
    assert len(record.revocation_checkpoint_sha256) == 64
    assert record.authorized_at == "2026-08-02T12:00:00Z"
    assert record.authorization_expires_at == "2026-08-03T12:00:00Z"
    assert len(record.step_records) == len(plan.steps)
    assert len(record.topology_reports) == 2
    assert all(item.matches for item in record.topology_reports)
    assert record.layout_hashes == (plan.expected_layout_hash, plan.expected_layout_hash)
    assert "checkpoint-validated" in record.boundary
    assert record.to_dict()["completed"] is True


def test_plain_base_plan_cannot_execute(tmp_path: Path) -> None:
    _, profile, envelope = authorization_context(tmp_path)
    base = compile_process_design(design(), profile)
    with pytest.raises(NativeBuildError, match="RuntimeQualifiedCompilationPlan"):
        execute_compilation_plan(
            base,  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            profile=profile,
            qualification_source=envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )


def test_authorization_fails_before_adapter_access(tmp_path: Path) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    (tmp_path / SIGNED_POLICY_FILENAME).unlink()

    class ExplodingAdapter:
        @property
        def profile_id(self) -> str:
            raise AssertionError("adapter must not be accessed before authorization")

    with pytest.raises(NativeBuildError, match="signed revocation policy is unavailable"):
        execute_compilation_plan(
            plan,
            ExplodingAdapter(),  # type: ignore[arg-type]
            profile=profile,
            qualification_source=envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )


def test_adapter_profile_identity_must_match(tmp_path: Path) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    adapter = FakeAdapter(plan)
    adapter._profile_id = "wrong"
    with pytest.raises(NativeBuildError, match="profile_id"):
        execute(plan, adapter, profile, envelope, tmp_path)

    adapter = FakeAdapter(plan)
    adapter._profile_hash = "0" * 64
    with pytest.raises(NativeBuildError, match="profile_hash"):
        execute(plan, adapter, profile, envelope, tmp_path)


def test_adapter_code_and_runtime_identity_must_match(tmp_path: Path) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    adapter = FakeAdapter(plan)
    adapter._adapter_code_sha256 = "0" * 64
    with pytest.raises(NativeBuildError, match="code hash"):
        execute(plan, adapter, profile, envelope, tmp_path)

    adapter = FakeAdapter(plan)
    adapter._runtime_identity_sha256 = "0" * 64
    with pytest.raises(NativeBuildError, match="runtime identity"):
        execute(plan, adapter, profile, envelope, tmp_path)


def test_topology_mismatch_fails_closed(tmp_path: Path) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    changed = replace(
        plan.expected_topology,
        nodes=(*plan.expected_topology.nodes, TopologyNode("EXTRA_001", "heater")),
        source="native-readback",
    )
    with pytest.raises(NativeBuildError, match="Topology readback mismatch"):
        execute(
            plan,
            FakeAdapter(plan, topology=changed),
            profile,
            envelope,
            tmp_path,
        )


def test_layout_mismatch_fails_closed(tmp_path: Path) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    with pytest.raises(NativeBuildError, match="Layout readback mismatch"):
        execute(
            plan,
            FakeAdapter(plan, layout_hash="0" * 64),
            profile,
            envelope,
            tmp_path,
        )


def test_non_object_step_result_fails_closed(tmp_path: Path) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    adapter = FakeAdapter(plan)
    first_apply = next(
        item
        for item in plan.steps
        if item.operation
        not in {
            "readback_topology",
            "readback_topology_after_reopen",
            "readback_layout",
            "readback_layout_after_reopen",
        }
    )
    adapter.override_results[first_apply.step_id] = "not-an-object"
    with pytest.raises(NativeBuildError, match="non-object"):
        execute(plan, adapter, profile, envelope, tmp_path)


def test_missing_mandatory_readback_fails_closed(tmp_path: Path) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    adapter = FakeAdapter(plan)
    first_apply = next(item for item in plan.steps if item.expected_readback)
    adapter.override_results[first_apply.step_id] = {}
    with pytest.raises(NativeBuildError, match="Mandatory readback failed"):
        execute(plan, adapter, profile, envelope, tmp_path)


def test_expected_subset_comparison() -> None:
    assert _contains_expected({"a": 1, "b": 2}, {"a": 1}) is True
    assert _contains_expected({"a": {"b": 1, "c": 2}}, {"a": {"b": 1}}) is True
    assert _contains_expected({"a": [1, 2]}, {"a": [1, 2]}) is True
    assert _contains_expected({"a": [1, 2]}, {"a": [1]}) is False
    assert _contains_expected([], {}) is False
    assert _contains_expected({"a": 1}, {"a": 2}) is False
