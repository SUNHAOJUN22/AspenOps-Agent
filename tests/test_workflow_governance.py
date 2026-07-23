from __future__ import annotations

import re
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
WORKFLOWS = {
    "ci.yml",
    "generate-performance-evidence.yml",
    "licensed-aspen-certification.yml",
    "windows-control-plane.yml",
}
UV_VERSION = "0.11.16"
PERFORMANCE_BASELINE_SHA = "ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2"
PINNED_ACTION = re.compile(
    r"^\s*(?:-\s+)?uses:\s+[^@\s]+@([0-9a-f]{40})(?:\s+#.*)?$",
)
WRITE_PERMISSION = re.compile(
    r"^\s+[A-Za-z][A-Za-z0-9_-]*:\s*write(?:\s+#.*)?$",
    re.MULTILINE,
)
INLINE_WRITE_PERMISSION = re.compile(
    r"\bpermissions\s*:\s*(?:write-all|\{[^}\n]*:\s*write\b)",
    re.IGNORECASE,
)
RUN_HEADER = re.compile(r"^(\s*)(?:-\s+)?run:\s*(.*)$")
BLOCK_SCALARS = {"|", "|-", "|+", ">", ">-", ">+"}


def workflow_text(name: str) -> str:
    return (WORKFLOW_DIR / name).read_text(encoding="utf-8")


def shell_commands(text: str) -> list[str]:
    """Return literal, folded, inline and shorthand Actions run commands."""

    lines = text.splitlines()
    commands: list[str] = []
    index = 0
    while index < len(lines):
        match = RUN_HEADER.match(lines[index])
        if match is None:
            index += 1
            continue
        parent_indent = len(match.group(1))
        suffix = match.group(2).strip()
        if suffix not in BLOCK_SCALARS:
            commands.append(suffix)
            index += 1
            continue
        block: list[str] = []
        index += 1
        while index < len(lines):
            line = lines[index]
            indent = len(line) - len(line.lstrip())
            if line.strip() and indent <= parent_indent:
                break
            block.append(line)
            index += 1
        commands.append("\n".join(block))
    return commands


def test_only_authoritative_long_lived_workflows_exist() -> None:
    observed = {path.name for path in WORKFLOW_DIR.glob("*.yml")}
    observed.update(path.name for path in WORKFLOW_DIR.glob("*.yaml"))
    assert observed == WORKFLOWS


def test_actions_runners_and_uv_are_immutable() -> None:
    for name in WORKFLOWS:
        text = workflow_text(name)
        uses_lines = [
            line
            for line in text.splitlines()
            if line.strip().startswith(("uses:", "- uses:"))
        ]
        assert uses_lines, f"{name} has no external action declarations"
        assert all(PINNED_ACTION.fullmatch(line) for line in uses_lines)
        chunks = text.split("astral-sh/setup-uv@")[1:]
        assert chunks, f"{name} has no setup-uv step"
        for chunk in chunks:
            step = chunk.split("\n      - ", 1)[0]
            assert f'version: "{UV_VERSION}"' in step

    portable = workflow_text("ci.yml")
    performance = workflow_text("generate-performance-evidence.yml")
    windows = workflow_text("windows-control-plane.yml")
    licensed = workflow_text("licensed-aspen-certification.yml")
    assert portable.count("runs-on: ubuntu-24.04") == 2
    assert "runs-on: ubuntu-24.04" in performance
    assert "runs-on: windows-2025" in windows
    assert licensed.count("runs-on: ubuntu-24.04") == 1
    assert "runs-on: [self-hosted, windows, x64, aspen-licensed]" in licensed
    assert "ubuntu-latest" not in portable + performance + licensed
    assert "windows-latest" not in windows


def test_workflows_are_read_only_frozen_and_fail_closed() -> None:
    for name in WORKFLOWS:
        text = workflow_text(name)
        assert "permissions:\n  contents: read" in text
        assert WRITE_PERMISSION.search(text) is None
        assert INLINE_WRITE_PERMISSION.search(text) is None
        assert "persist-credentials: false" in text
        assert "pull_request_target:" not in text
        assert "continue-on-error: true" not in text
        assert "uv lock --check" in text
        assert "uv sync --frozen" in text

    for name in ("ci.yml", "generate-performance-evidence.yml"):
        commands = shell_commands(workflow_text(name))
        assert commands
        assert all("set -euo pipefail" in command for command in commands)
        assert all("set -o pipefail" not in command for command in commands)


def test_dispatch_inputs_never_interpolate_into_run_commands() -> None:
    for name in WORKFLOWS:
        for command in shell_commands(workflow_text(name)):
            assert "${{ inputs." not in command


def test_ci_collects_all_dependency_audit_evidence_before_failing() -> None:
    text = workflow_text("ci.yml")
    assert text.count("uv audit --frozen") == 1
    assert "UV_PREVIEW_FEATURES: json-output" in text
    assert tuple(map(int, UV_VERSION.split("."))) >= (0, 11, 15)
    assert "for platform in linux windows; do" in text
    assert "for version in 3.11 3.12 3.13; do" in text
    assert 'stem="var/ci/dependency-audit-${platform}-py${version}"' in text
    assert 'output="${stem}.json"' in text
    assert 'error_log="${stem}.log"' in text
    assert 'if ! python -m json.tool "$output" >/dev/null' in text
    assert "One or more locked dependency audits failed" in text
    assert text.index("for platform in linux windows; do") < text.index(
        'if [[ "$audit_failed" -ne 0 ]]'
    )


def test_performance_revisions_environments_and_evidence_are_isolated() -> None:
    text = workflow_text("generate-performance-evidence.yml")
    guard = text.index("Reject non-main manual dispatch")
    checkout = text.index("actions/checkout@")
    trust = text.index("Verify trusted revisions and prepare isolated checkouts")
    setup = text.index("astral-sh/setup-uv@")
    sync = text.index("Verify lockfiles and sync isolated benchmark environments")
    baseline = text.index("Run baseline matrix in baseline environment")
    candidate = text.index("Run candidate matrix in candidate environment")

    assert f"default: {PERFORMANCE_BASELINE_SHA}" in text
    assert "if: ${{ github.ref == 'refs/heads/main' }}" not in text
    assert guard < checkout < trust < setup < sync < baseline < candidate
    assert "Performance evidence must be dispatched from refs/heads/main" in text
    assert 'printf \'%s\\n\' "$GITHUB_REF" > "$evidence_dir/dispatch-ref.txt"' in text
    assert 'tee "$evidence_dir/dispatch-guard.log"' in text
    assert "ref: ${{ inputs.candidate_ref }}" not in text
    assert 'git rev-parse --verify --end-of-options "${BASELINE_REF}^{commit}"' in text
    assert 'git rev-parse --verify --end-of-options "${CANDIDATE_REF}^{commit}"' in text
    assert 'git merge-base --is-ancestor "$candidate_sha" origin/main' in text
    assert 'git merge-base --is-ancestor "$baseline_sha" origin/main' in text
    assert 'git merge-base --is-ancestor "$baseline_sha" "$candidate_sha"' in text
    assert 'git checkout --detach "$candidate_sha"' in text
    assert 'git worktree add --detach /tmp/aspenops-baseline "$baseline_sha"' in text

    job_env = text[text.index("    env:") : text.index("    steps:")]
    assert "runner.temp" not in job_env
    evidence_assignment = 'evidence_dir="${RUNNER_TEMP}/aspenops-performance-evidence"'
    assert text.count(evidence_assignment) == 7
    assert 'rm -rf "$evidence_dir"' in text
    assert 'mkdir -p "$evidence_dir"' in text
    assert "var/benchmarks" not in text
    assert "PYTHONPATH: /tmp/aspenops-baseline/src" not in text
    assert "candidate-uv-lock.log" in text
    assert "baseline-uv-lock.log" in text
    assert "candidate-sync.log" in text
    assert "baseline-sync.log" in text
    assert "/tmp/aspenops-baseline/.venv/bin/python" in text
    assert "/tmp/aspenops-baseline/scripts/run_benchmark_matrix.py" in text
    assert ".venv/bin/python scripts/run_benchmark_matrix.py" in text
    assert "name: performance-evidence-${{ github.run_id }}" in text
    assert "path: ${{ runner.temp }}/aspenops-performance-evidence" in text
    assert "name: performance-evidence-${{ inputs." not in text


def test_licensed_paths_are_canonicalized_before_real_execution() -> None:
    workflow = workflow_text("licensed-aspen-certification.yml")
    gate = Path("scripts/validate_licensed_paths.py").read_text(encoding="utf-8")
    dispatch_guard = workflow.index("dispatch-guard:")
    guard_step = workflow.index("Require refs/heads/main")
    certify = workflow.index("  certify:")
    checkout = workflow.index("Checkout trusted workflow revision")
    trust = workflow.index("Verify and checkout exact revision from main")
    setup = workflow.index("Set up Python")

    assert "if: ${{ github.ref == 'refs/heads/main' }}" not in workflow
    assert "needs: dispatch-guard" in workflow
    assert dispatch_guard < guard_step < certify < checkout < trust < setup
    assert "Licensed certification must be dispatched from refs/heads/main" in workflow
    assert "runs-on: ubuntu-24.04" in workflow[dispatch_guard:certify]
    assert "ref: ${{ inputs.expected_head_sha }}" not in workflow
    assert "PLAN_PATH: ${{ inputs.plan_path }}" in workflow
    assert "EXPECTED_HEAD_SHA: ${{ inputs.expected_head_sha }}" in workflow
    assert "EXECUTION_APPROVED: ${{ inputs.approve_real_execution }}" in workflow
    assert "plan_path must be one non-empty line" in workflow
    assert "plan_path must be repository-relative" in workflow
    assert 'git rev-parse --verify --end-of-options "$expected^{commit}"' in workflow
    assert "git merge-base --is-ancestor $expected origin/main" in workflow
    assert "git checkout --detach $expected" in workflow
    assert "python scripts/validate_licensed_paths.py" in workflow
    assert '"PLAN_PATH=$($resolved.plan_path)"' in workflow
    assert '"ASPENOPS_STATE_DIR=$($resolved.state_dir)"' in workflow
    assert "GITHUB_WORKSPACE must be absolute" in gate
    assert "Every ASPENOPS_ALLOWED_ROOTS entry must be absolute" in gate
    assert "ASPENOPS_STATE_DIR must be absolute" in gate
    assert "PLAN_PATH resolves outside GITHUB_WORKSPACE" in gate
    assert "ASPENOPS_STATE_DIR resolves outside ASPENOPS_ALLOWED_ROOTS" in gate


def test_licensed_evidence_is_clean_and_workspace_scoped() -> None:
    text = workflow_text("licensed-aspen-certification.yml")
    staging = text.index("Stage and verify licensed evidence")
    upload = text.index("Upload signed licensed evidence")
    block = text[staging:upload]
    upload_block = text[upload:]
    assert "if: ${{ success() }}" in block
    assert "Test-Path -LiteralPath $source -PathType Leaf" in block
    assert "(Get-Item -LiteralPath $source).Length -le 0" in block
    assert "var/ci/licensed-evidence" in block
    assert "Remove-Item -LiteralPath $staging" in block
    assert "Copy-Item -LiteralPath $preflight" in block
    assert "Copy-Item -LiteralPath $report" in block
    assert "Copy-Item -LiteralPath $bundle" in block
    assert "Staged licensed evidence is missing" in block
    assert "Staged licensed evidence is empty" in block
    assert "name: licensed-${{ inputs.backend }}-${{ github.run_id }}" in upload_block
    assert "path: var/ci" in upload_block
    assert "${{ env.ASPENOPS_STATE_DIR }}" not in upload_block
    assert "expected_head_sha" not in upload_block


def test_windows_gates_keep_policy_documentation_and_bootstrap_contracts() -> None:
    for name in ("windows-control-plane.yml", "licensed-aspen-certification.yml"):
        text = workflow_text(name)
        assert "tests/test_config_resource_budgets.py" in text
        assert "tests/test_documentation_contracts.py" in text
        assert "tests/test_real_backend_state_policy.py" in text
        assert "tests/test_licensed_path_gate.py" in text
    windows = workflow_text("windows-control-plane.yml")
    assert "Parse PowerShell bootstrap" in windows
    assert "System.Management.Automation.Language.Parser" in windows
    assert "Exercise PowerShell bootstrap helpers" in windows
    assert ". ./scripts/setup_windows.ps1 -LibraryMode" in windows
    assert "Duplicate dotenv failure leaked a raw secret" in windows
    assert "Unbalanced dotenv failure leaked a raw secret" in windows
    assert "winget upgrade/install fallback order was not preserved" in windows


def test_windows_bootstrap_is_frozen_fail_closed_and_secret_safe() -> None:
    text = Path("scripts/setup_windows.ps1").read_text(encoding="utf-8")
    assert "[switch]$LibraryMode" in text
    assert "if (-not $LibraryMode)" in text
    assert "Set-StrictMode -Version Latest" in text
    assert '$RequiredUvVersion = [version]"0.11.16"' in text
    assert "Try-UvSelfUpdate" in text
    assert "uv self update" in text
    assert '$env:UV_NO_MODIFY_PATH = "1"' in text
    assert 'Invoke-WingetUv -Verb "upgrade"' in text
    assert 'Invoke-WingetUv -Verb "install"' in text
    assert "uv lock --check" in text
    assert "uv sync --frozen --extra windows --extra agent --extra dev --extra signing" in text
    assert "Import-DotEnv -Path .env" in text
    assert text.index("Import-DotEnv -Path .env") < text.index("aspenops doctor --probe")
    assert "Invalid .env entry: $entry" not in text
    assert "Invalid .env entry at line $lineNumber" in text
    assert "Duplicate environment variable at line $lineNumber" in text
    assert "Unbalanced quoted value at line $lineNumber" in text
    assert "if ($LASTEXITCODE -ne 0)" in text
