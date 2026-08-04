from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC
from pathlib import Path

import pytest

from aspenops_nexus.revocation_witness import (
    RevocationWitnessStatement,
    verify_revocation_witness,
)
from aspenops_nexus.runtime_execution_authorization import (
    _bounded_unique_digests,
    _bounded_unique_key_ids,
    _bounded_unique_texts,
    _utc_now,
    authorize_runtime_execution,
)
from test_revocation_witness import NOW, verified_witness
from test_runtime_execution_authorization import context


def _forge_plan_identity(plan: object, field: str, replacement: str) -> object:
    qualification = plan.qualification  # type: ignore[attr-defined]
    if field == "qualification_evidence_sha256":
        forged_qualification = replace(qualification, evidence_sha256=replacement)
    elif field == "qualification_key_id":
        forged_qualification = replace(qualification, signing_key_id=replacement)
    elif field in {"adapter_code_sha256", "runtime_identity_sha256"}:
        forged_statement = replace(
            qualification.statement,
            **{field: replacement},
        )
        forged_qualification = replace(qualification, statement=forged_statement)
    else:  # pragma: no cover - the parametrization is intentionally closed.
        raise AssertionError(f"Unsupported identity field: {field}")
    return replace(plan, qualification=forged_qualification)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        (
            "qualification_evidence_sha256",
            "0" * 64,
            "evidence hash changed",
        ),
        (
            "qualification_key_id",
            "0" * 32,
            "signing key changed",
        ),
        (
            "adapter_code_sha256",
            "0" * 64,
            "adapter-code hash changed",
        ),
        (
            "runtime_identity_sha256",
            "0" * 64,
            "identity hash changed",
        ),
    ],
)
def test_fresh_authorization_rechecks_plan_identity_fields(
    tmp_path: Path,
    field: str,
    replacement: str,
    message: str,
) -> None:
    plan, profile, envelope, _ = context(tmp_path)
    forged = _forge_plan_identity(plan, field, replacement)
    with pytest.raises(ValueError, match=message):
        authorize_runtime_execution(
            forged,  # type: ignore[arg-type]
            profile,
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )


def test_witness_verification_accepts_bytes_and_path_sources(tmp_path: Path) -> None:
    _, _, expected, envelope, _, public_pem = verified_witness()
    payload = json.dumps(envelope, sort_keys=True).encode("utf-8")
    assert (
        verify_revocation_witness(
            payload,
            trusted_public_key=public_pem,
            now=NOW,
        )
        == expected
    )

    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(payload)
    assert (
        verify_revocation_witness(
            receipt,
            trusted_public_key=public_pem,
            now=NOW,
        )
        == expected
    )


def test_witness_verification_rejects_non_object_and_bad_envelope() -> None:
    _, _, _, _, _, public_pem = verified_witness()
    with pytest.raises(ValueError, match="root must be an object"):
        verify_revocation_witness(
            b"[]",
            trusted_public_key=public_pem,
            now=NOW,
        )
    with pytest.raises(ValueError, match="contain exactly"):
        verify_revocation_witness(
            {"schema": "incomplete"},
            trusted_public_key=public_pem,
            now=NOW,
        )


def test_witness_statement_parser_rejects_additional_input_shapes() -> None:
    _, _, verified, _, _, _ = verified_witness()
    document = verified.statement.to_dict()

    with pytest.raises(ValueError, match="must be an object"):
        RevocationWitnessStatement.from_dict([])

    bad_schema = dict(document)
    bad_schema["schema"] = "unsupported"
    with pytest.raises(ValueError, match="unsupported"):
        RevocationWitnessStatement.from_dict(bad_schema)

    bool_sequence = dict(document)
    bool_sequence["policy_sequence"] = True
    with pytest.raises(ValueError, match="positive"):
        RevocationWitnessStatement.from_dict(bool_sequence)


def test_witness_match_reports_policy_evidence_and_authority_drift() -> None:
    policy, checkpoint, witness, _, _, _ = verified_witness()

    changed_evidence = replace(policy, evidence_sha256="f" * 64)
    with pytest.raises(ValueError, match="policy_evidence_sha256"):
        witness.assert_matches(changed_evidence, checkpoint)

    changed_authority = replace(policy, signing_key_id="f" * 32)
    with pytest.raises(ValueError, match="policy_signing_key_id"):
        witness.assert_matches(changed_authority, checkpoint)


def test_runtime_authorization_helper_rejection_branches() -> None:
    current = _utc_now(None, "current time")
    assert current.tzinfo is UTC

    for helper in (
        _bounded_unique_texts,
        _bounded_unique_digests,
        _bounded_unique_key_ids,
    ):
        with pytest.raises(ValueError, match="must be an array"):
            helper("not-an-array", "items")
        with pytest.raises(ValueError, match="exceeds"):
            helper(["a"] * 10_001, "items")
