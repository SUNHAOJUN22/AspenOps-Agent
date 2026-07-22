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


def test_licensed_workflow_checks_out_only_a_trusted_main_ancestor() -> None:
    text = workflow_text()

    assert f"actions/checkout@{CHECKOUT_SHA}" in text
    assert f"astral-sh/setup-uv@{SETUP_UV_SHA}" in text
    assert f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}" in text
    assert "ref: ${{ inputs.expected_head_sha }}" in text
    assert "persist-credentials: false" in text
    assert "git rev-parse HEAD" in text
    assert "^[0-9a-f]{40}$" in text
    assert "+refs/heads/main:refs/remotes/origin/main" in text
    assert "git merge-base --is-ancestor $expected origin/main" in text
    assert "not an ancestor of the trusted main branch" in text
    assert "permissions:\n  contents: read" in text
    assert "git push" not in text
    assert "git merge " not in text


def test_inputs_and_filesystem_targets_are_canonicalized_before_execution() -> None:
    text = workflow_text()

    assert "PLAN_PATH: ${{ inputs.plan_path }}" in text
    assert "EXPECTED_HEAD_SHA: ${{ inputs.expected_head_sha }}" in text
    assert "EXECUTION_APPROVED: ${{ inputs.approve_real_execution }}" in text
    assert '$expected = "${{ inputs.expected_head_sha }}"' not in text
    assert '"${{ inputs.plan_path }}"' not in text
    assert "plan_path must be one non-empty line" in text
    assert "plan_path must be repository-relative" in text
    assert "plan_path escapes the repository workspace" in text
    assert "python scripts/validate_licensed_paths.py" in text
    assert '"PLAN_PATH=$($resolved.plan_path)"' in text
    assert '"ASPENOPS_STATE_DIR=$($resolved.state_dir)"' in text
    assert '"$env:PLAN_PATH"' in text


def test_real_secrets_are_not_exposed_to_sync_or_mock_regression() -> None:
    text = workflow_text()
    steps = text.index("    steps:")
    sync = text.index("Verify lockfile and sync frozen certification dependencies")
    regression = text.index("Run isolated licensed control-plane regression gate")
    resolve_paths = text.index("Resolve licensed filesystem targets")
    preflight = text.index("Run licensed certification preflight")
    execute = text.index("Execute scoped licensed certification plan")

    assert "secrets." not in text[:steps]
    assert "secrets." not in text[sync:preflight]
    assert 'ASPENOPS_ALLOWED_ROOTS: ""' in text[regression:resolve_paths]
    assert text.count("${{ secrets.ASPENOPS_CERT_SIGNING_KEY_PATH }}") == 2
    assert "${{ secrets.ASPENOPS_CERT_SIGNING_KEY_PATH }}" in text[preflight:execute]
    assert "${{ secrets.ASPENOPS_CERT_SIGNING_KEY_PATH }}" in text[execute:]


def test_regression_and_path_gates_precede_real_execution() -> None:
    text = workflow_text()
    checkout = text.index("Checkout exact approved commit")
    trust = text.index("Verify exact revision belongs to main")
    setup = text.index("Set up Python")
    sync = text.index("Verify lockfile and sync frozen certification dependencies")
    regression = text.index("Run isolated licensed control-plane regression gate")
    resolve_paths = text.index("Resolve licensed filesystem targets")
    preflight = text.index("aspenops certification-preflight")
    approval = text.index("Preflight completed, but licensed COM execution")
    execute = text.index("aspenops certify-licensed")
    verify = text.index("aspenops verify-licensed-bundle")
    completeness = text.index("Verify licensed evidence completeness")
    upload = text.index("Upload signed licensed evidence")

    assert (
        checkout
        < trust
        < setup
        < sync
        < regression
        < resolve_paths
        < preflight
        < approval
        < execute
        < verify
        < completeness
        < upload
    )
    assert "uv lock --check" in text
    assert (
        "uv sync --frozen --extra dev --extra windows --extra agent --extra signing" in text
    )
    assert "ASPENOPS_BACKEND: mock" in text
    assert r"ASPENOPS_STATE_DIR: ${{ github.workspace }}\var\licensed-regression" in text
    assert "tests/test_batch_backend_default.py" in text
    assert "tests/test_cli_output_policy.py" in text
    assert "tests/test_real_backend_state_policy.py" in text
    assert "tests/test_licensed_path_gate.py" in text
    assert "tests/test_licensed_certification.py" in text
    assert "tests/test_licensed_certification_governance.py" in text
    assert "tests/test_aspen_process_ownership.py" in text
    assert "tests/test_workflow_governance.py" in text
    assert "tests/test_wheel_smoke_governance.py" in text
    assert "licensed-software-regression.xml" in text


def test_workflow_cannot_self_grant_real_certification() -> None:
    text = workflow_text()

    assert "PENDING_REAL_ASPEN_CERTIFICATION" in text
    assert "REAL_ASPEN_CERTIFIED" not in text
    assert "Runtime is not permitted to self-grant" in text


def test_complete_signed_evidence_is_required_before_upload() -> None:
    text = workflow_text()
    completeness = text.index("Verify licensed evidence completeness")
    upload = text.index("Upload signed licensed evidence")
    block = text[completeness:upload]

    assert "if: ${{ success() }}" in block
    assert "Test-Path -LiteralPath $path -PathType Leaf" in block
    assert "(Get-Item -LiteralPath $path).Length -le 0" in block
    assert "Required licensed evidence file is missing" in block
    assert "Required licensed evidence file is empty" in block
    assert "if-no-files-found: error" in text[upload:]


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
