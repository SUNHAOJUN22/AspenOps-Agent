from __future__ import annotations

from pathlib import Path

CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_UV_SHA = "d0cc045d04ccac9d8b7881df0226f9e82c39688e"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"


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

    assert f"actions/checkout@{CHECKOUT_SHA}" in text
    assert f"astral-sh/setup-uv@{SETUP_UV_SHA}" in text
    assert f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}" in text
    assert "ref: ${{ inputs.expected_head_sha }}" in text
    assert "persist-credentials: false" in text
    assert "git rev-parse HEAD" in text
    assert "^[0-9a-f]{40}$" in text
    assert "permissions:\n  contents: read" in text
    assert "git push" not in text
    assert "merge" not in text.casefold()


def test_inputs_are_environment_bound_and_plan_path_is_canonicalized() -> None:
    text = workflow_text()

    assert "PLAN_PATH: ${{ inputs.plan_path }}" in text
    assert "EXPECTED_HEAD_SHA: ${{ inputs.expected_head_sha }}" in text
    assert "EXECUTION_APPROVED: ${{ inputs.approve_real_execution }}" in text
    assert '$expected = "${{ inputs.expected_head_sha }}"' not in text
    assert '"${{ inputs.plan_path }}"' not in text
    assert "plan_path must be one non-empty line" in text
    assert "plan_path must be repository-relative" in text
    assert "plan_path escapes the repository workspace" in text
    assert '"PLAN_PATH=$plan" | Out-File -FilePath $env:GITHUB_ENV' in text
    assert '"$env:PLAN_PATH"' in text


def test_regression_and_preflight_precede_approval_execution_and_verification() -> None:
    text = workflow_text()
    regression = text.index("Run licensed control-plane regression gate")
    preflight = text.index("aspenops certification-preflight")
    approval = text.index("Preflight completed, but licensed COM execution")
    execute = text.index("aspenops certify-licensed")
    verify = text.index("aspenops verify-licensed-bundle")

    assert regression < preflight < approval < execute < verify
    assert "uv lock --check" in text
    assert (
        "uv sync --frozen --extra dev --extra windows --extra agent --extra signing" in text
    )
    assert "ASPENOPS_BACKEND: mock" in text
    assert r"ASPENOPS_STATE_DIR: ${{ github.workspace }}\var\licensed-regression" in text
    assert "tests/test_licensed_certification.py" in text
    assert "tests/test_licensed_certification_governance.py" in text
    assert "tests/test_aspen_process_ownership.py" in text
    assert "tests/test_workflow_governance.py" in text
    assert "licensed-software-regression.xml" in text
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

    assert "name: licensed-${{ inputs.backend }}-${{ github.run_id }}" in upload
    assert "expected_head_sha" not in upload
    assert "licensed-software-regression.xml" in upload
    assert "preflight.json" in upload
    assert "licensed-certification-report.json" in upload
    assert "licensed-certification-bundle.zip" in upload
    assert "ASPENOPS_CERT_SIGNING_KEY" not in upload
    assert "private" not in upload.casefold()
