from __future__ import annotations

from pathlib import Path


def workflow_text() -> str:
    return Path(".github/workflows/licensed-aspen-certification.yml").read_text(encoding="utf-8")


def test_licensed_workflow_is_manual_protected_and_self_hosted() -> None:
    text = workflow_text()

    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "branches:" not in text
    assert "runs-on: [self-hosted, windows, x64, aspen-licensed]" in text
    assert "environment: licensed-aspen-certification" in text
    assert "approve_real_execution:" in text
    assert "cancel-in-progress: false" in text
    assert 'ASPENOPS_VISIBLE: "false"' in text
    assert 'ASPENOPS_CACHE_FAILURES: "false"' in text


def test_licensed_workflow_checks_out_exact_commit_without_write_credentials() -> None:
    text = workflow_text()

    assert "ref: ${{ inputs.expected_head_sha }}" in text
    assert "persist-credentials: false" in text
    assert "git rev-parse HEAD" in text
    assert "^[0-9a-f]{40}$" in text
    assert "permissions:\n  contents: read" in text
    assert "git push" not in text
    assert "merge" not in text.casefold()


def test_preflight_precedes_approval_execution_and_signed_verification() -> None:
    text = workflow_text()
    preflight = text.index("aspenops certification-preflight")
    approval = text.index("Preflight completed, but licensed COM execution")
    execute = text.index("aspenops certify-licensed")
    verify = text.index("aspenops verify-licensed-bundle")

    assert preflight < approval < execute < verify
    assert "uv sync --extra dev --extra windows --extra signing" in text
    assert "ASPENOPS_CERT_SIGNING_KEY_PATH" in text
    assert "ASPENOPS_CERT_PUBLIC_KEY_PATH" in text


def test_workflow_cannot_self_grant_real_certification() -> None:
    text = workflow_text()

    assert "PENDING_REAL_ASPEN_CERTIFICATION" in text
    assert "REAL_ASPEN_CERTIFIED" not in text
    assert "Runtime is not permitted to self-grant" in text


def test_uploaded_artifact_excludes_private_key_and_contains_signed_evidence() -> None:
    text = workflow_text()
    upload = text[text.index("Upload signed licensed evidence") :]

    assert "preflight.json" in upload
    assert "licensed-certification-report.json" in upload
    assert "licensed-certification-bundle.zip" in upload
    assert "ASPENOPS_CERT_SIGNING_KEY" not in upload
    assert "private" not in upload.casefold()
