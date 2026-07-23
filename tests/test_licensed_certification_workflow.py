from __future__ import annotations

from pathlib import Path

CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_UV_SHA = "d0cc045d04ccac9d8b7881df0226f9e82c39688e"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"


def workflow_text() -> str:
    return Path(".github/workflows/licensed-aspen-certification.yml").read_text(
        encoding="utf-8"
    )


def test_workflow_has_explicit_main_ref_guard_before_self_hosted_job() -> None:
    text = workflow_text()
    dispatch_guard = text.index("dispatch-guard:")
    guard_step = text.index("Require refs/heads/main")
    certify = text.index("  certify:")

    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "branches:" not in text
    assert "if: ${{ github.ref == 'refs/heads/main' }}" not in text
    assert "Licensed certification must be dispatched from refs/heads/main" in text
    assert "runs-on: ubuntu-24.04" in text[dispatch_guard:certify]
    assert "needs: dispatch-guard" in text[certify:]
    assert dispatch_guard < guard_step < certify
    assert "runs-on: [self-hosted, windows, x64, aspen-licensed]" in text
    assert "environment: licensed-aspen-certification" in text
    assert "approve_real_execution:" in text
    assert "concurrency:\n  group: licensed-aspen-certification" in text
    assert "licensed-aspen-certification-${{ inputs.backend }}" not in text
    assert "cancel-in-progress: false" in text


def test_approved_sha_is_bound_to_dispatched_workflow_revision() -> None:
    text = workflow_text()
    checkout = text.index("Checkout trusted workflow revision")
    trust = text.index("Verify dispatched revision and approved SHA")
    setup = text.index("Set up Python")

    assert f"actions/checkout@{CHECKOUT_SHA}" in text
    assert f"astral-sh/setup-uv@{SETUP_UV_SHA}" in text
    assert f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}" in text
    assert "ref: ${{ inputs.expected_head_sha }}" not in text
    assert "persist-credentials: false" in text
    assert checkout < trust < setup
    assert '$workflowSha = $env:GITHUB_SHA.Trim().ToLowerInvariant()' in text
    assert "expected_head_sha must equal the dispatched main GITHUB_SHA" in text
    assert "Initial checkout does not match the dispatched workflow revision" in text
    assert 'git rev-parse --verify --end-of-options "$workflowSha^{commit}"' in text
    assert "git merge-base --is-ancestor $workflowSha origin/main" in text
    assert "git checkout --detach $workflowSha" in text
    assert "Checked-out commit does not match the dispatched workflow revision" in text
    assert 'git rev-parse --verify --end-of-options "$expected^{commit}"' not in text
    assert "git checkout --detach $expected" not in text
    assert "permissions:\n  contents: read" in text
    assert "git push" not in text
    assert "git merge " not in text


def test_inputs_and_paths_are_canonicalized_before_real_execution() -> None:
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
    assert '"LICENSED_EVIDENCE_DIR=$evidenceDir"' in text
    assert '"$env:PLAN_PATH"' in text


def test_real_secrets_are_not_exposed_to_setup_or_mock_regression() -> None:
    text = workflow_text()
    sync = text.index("Verify lockfile and sync frozen certification dependencies")
    regression = text.index("Run isolated licensed control-plane regression gate")
    resolve_paths = text.index("Resolve licensed filesystem targets")
    preflight = text.index("Run licensed certification preflight")
    execute = text.index("Execute scoped licensed certification plan")

    assert "secrets." not in text[:preflight]
    assert "secrets." not in text[sync:preflight]
    assert 'ASPENOPS_ALLOWED_ROOTS: ""' in text[regression:resolve_paths]
    assert text.count("${{ secrets.ASPENOPS_CERT_SIGNING_KEY_PATH }}") == 2
    assert "${{ secrets.ASPENOPS_CERT_SIGNING_KEY_PATH }}" in text[preflight:execute]
    assert "${{ secrets.ASPENOPS_CERT_SIGNING_KEY_PATH }}" in text[execute:]


def test_software_gates_precede_real_execution_and_upload() -> None:
    text = workflow_text()
    ordered = [
        "Reject non-main manual dispatch",
        "Checkout trusted workflow revision",
        "Verify dispatched revision and approved SHA",
        "Set up Python",
        "Verify lockfile and sync frozen certification dependencies",
        "Run isolated licensed control-plane regression gate",
        "Resolve licensed filesystem targets",
        "aspenops certification-preflight",
        "Preflight completed, but licensed COM execution",
        "aspenops certify-licensed",
        "aspenops verify-licensed-bundle",
        "Stage and verify licensed evidence",
        "Upload signed licensed evidence",
    ]
    positions = [text.index(marker) for marker in ordered]
    assert positions == sorted(positions)
    assert "uv lock --check" in text
    sync_command = (
        "uv sync --frozen --extra dev --extra windows --extra agent --extra signing"
    )
    assert sync_command in text
    assert "ASPENOPS_BACKEND: mock" in text
    mock_state = r"ASPENOPS_STATE_DIR: ${{ github.workspace }}\var\licensed-regression"
    assert mock_state in text
    assert "Remove-Item -LiteralPath var/ci -Recurse -Force" in text
    assert "tests/test_documentation_contracts.py" in text
    assert "tests/test_workflow_governance.py" in text
    assert "licensed-software-regression.xml" in text


def test_external_evidence_is_isolated_per_run_attempt() -> None:
    text = workflow_text()
    resolve = text.index("Resolve licensed filesystem targets")
    preflight = text.index("Run licensed certification preflight")
    block = text[resolve:preflight]

    assert '$runScope = "$env:GITHUB_RUN_ID-$env:GITHUB_RUN_ATTEMPT"' in block
    assert '$evidenceRoot = Join-Path $resolved.state_dir "licensed-certification"' in block
    assert "$evidenceDir = Join-Path $evidenceRoot $runScope" in block
    assert "Remove-Item -LiteralPath $evidenceDir -Recurse -Force" in block
    assert block.index("Remove-Item -LiteralPath $evidenceDir") < block.index(
        "New-Item -ItemType Directory -Force $evidenceDir"
    )
    assert '"LICENSED_EVIDENCE_DIR=$evidenceDir"' in block
    assert '$env:LICENSED_EVIDENCE_DIR\preflight.json' in text
    assert '$env:LICENSED_EVIDENCE_DIR\licensed-certification-report.json' in text
    assert '$env:LICENSED_EVIDENCE_DIR\licensed-certification-bundle.zip' in text
    assert '$env:ASPENOPS_STATE_DIR\licensed-certification' not in text


def test_workflow_cannot_self_grant_real_certification() -> None:
    text = workflow_text()
    assert "PENDING_REAL_ASPEN_CERTIFICATION" in text
    assert "REAL_ASPEN_CERTIFIED" not in text
    assert "Runtime is not permitted to self-grant" in text


def test_evidence_is_clean_validated_and_workspace_scoped() -> None:
    text = workflow_text()
    staging = text.index("Stage and verify licensed evidence")
    upload = text.index("Upload signed licensed evidence")
    block = text[staging:upload]
    upload_block = text[upload:]

    assert "if: ${{ success() }}" in block
    assert "Test-Path -LiteralPath $source -PathType Leaf" in block
    assert "(Get-Item -LiteralPath $source).Length -le 0" in block
    assert "Required licensed evidence is missing" in block
    assert "Required licensed evidence is empty" in block
    assert "var/ci/licensed-evidence" in block
    assert "Remove-Item -LiteralPath $staging -Recurse -Force" in block
    assert block.index("Remove-Item -LiteralPath $staging") < block.index(
        "New-Item -ItemType Directory -Force $staging"
    )
    assert "Copy-Item -LiteralPath $preflight" in block
    assert "Copy-Item -LiteralPath $report" in block
    assert "Copy-Item -LiteralPath $bundle" in block
    assert "Staged licensed evidence is missing" in block
    assert "Staged licensed evidence is empty" in block
    artifact_name = (
        "name: licensed-${{ inputs.backend }}-${{ github.run_id }}-"
        "${{ github.run_attempt }}"
    )
    assert artifact_name in upload_block
    assert "expected_head_sha" not in upload_block
    assert "path: var/ci" in upload_block
    assert "${{ env.ASPENOPS_STATE_DIR }}" not in upload_block
    assert "ASPENOPS_CERT_SIGNING_KEY" not in upload_block
