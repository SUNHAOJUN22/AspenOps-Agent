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
PINNED_ACTION = re.compile(
    r"^\s*(?:-\s+)?uses:\s+[^@\s]+@([0-9a-f]{40})(?:\s+#.*)?$",
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


def test_all_external_actions_are_pinned_to_full_commit_shas() -> None:
    for name in WORKFLOWS:
        uses_lines = [
            line
            for line in workflow_text(name).splitlines()
            if line.strip().startswith(("uses:", "- uses:"))
        ]
        assert uses_lines, f"{name} has no external action declarations"
        for line in uses_lines:
            match = PINNED_ACTION.fullmatch(line)
            assert match is not None, f"Unpinned action in {name}: {line.strip()}"


def test_all_setup_uv_steps_pin_the_exact_tool_version() -> None:
    expected = f'version: "{UV_VERSION}"'
    for name in WORKFLOWS:
        text = workflow_text(name)
        chunks = text.split("astral-sh/setup-uv@")[1:]
        assert chunks, f"{name} has no setup-uv step"
        for chunk in chunks:
            step = chunk.split("\n      - ", 1)[0]
            assert expected in step, f"{name} does not pin uv {UV_VERSION}"


def test_ci_audits_every_supported_python_platform_combination() -> None:
    text = workflow_text("ci.yml")
    assert text.count("uv audit --frozen") == 1
    assert "UV_PREVIEW_FEATURES: json-output" in text
    assert tuple(map(int, UV_VERSION.split("."))) >= (0, 11, 15)
    assert "for platform in linux windows; do" in text
    assert "for version in 3.11 3.12 3.13; do" in text
    assert 'stem="var/ci/dependency-audit-${platform}-py${version}"' in text
    assert 'output="${stem}.json"' in text
    assert 'error_log="${stem}.log"' in text
    assert "audit_failed=0" in text
    assert "if ! uv audit --frozen" in text
    assert '> "$output" 2> "$error_log"' in text
    assert 'if ! python -m json.tool "$output" >/dev/null' in text
    assert "audit_failed=1" in text
    assert "One or more locked dependency audits failed" in text
    assert text.index("for platform in linux windows; do") < text.index(
        'if [[ "$audit_failed" -ne 0 ]]'
    )


def test_hosted_runner_os_versions_are_explicit() -> None:
    portable = workflow_text("ci.yml")
    performance = workflow_text("generate-performance-evidence.yml")
    windows = workflow_text("windows-control-plane.yml")

    assert portable.count("runs-on: ubuntu-24.04") == 2
    assert "ubuntu-latest" not in portable
    assert "runs-on: ubuntu-24.04" in performance
    assert "ubuntu-latest" not in performance
    assert "runs-on: windows-2025" in windows
    assert "windows-latest" not in windows


def test_all_bash_steps_explicitly_fail_closed() -> None:
    for name in ("ci.yml", "generate-performance-evidence.yml"):
        commands = shell_commands(workflow_text(name))
        assert commands
        for command in commands:
            assert "set -euo pipefail" in command, f"Weak Bash mode in {name}"
            assert "set -o pipefail" not in command


def test_workflows_are_read_only_and_do_not_retain_checkout_credentials() -> None:
    for name in WORKFLOWS:
        text = workflow_text(name)
        assert "permissions:\n  contents: read" in text
        assert "persist-credentials: false" in text
        assert "pull_request_target:" not in text
        assert "continue-on-error: true" not in text
        assert "contents: write" not in text


def test_all_workflows_use_checked_frozen_dependencies() -> None:
    for name in WORKFLOWS:
        text = workflow_text(name)
        assert "uv lock --check" in text
        assert "uv sync --frozen" in text


def test_dispatch_inputs_never_interpolate_into_any_run_command() -> None:
    for name in WORKFLOWS:
        for command in shell_commands(workflow_text(name)):
            assert "${{ inputs." not in command, (
                f"Direct input interpolation in {name} run command"
            )


def test_performance_revisions_are_trusted_before_code_execution() -> None:
    text = workflow_text("generate-performance-evidence.yml")
    trust_step = text.index("Verify trusted revisions and prepare baseline worktree")
    tool_setup = text.index("astral-sh/setup-uv@")
    dependency_sync = text.index("uv sync --frozen")

    assert "group: aspenops-performance-evidence" in text
    assert "group: aspenops-performance-${{ inputs." not in text
    assert "BASELINE_REF: ${{ inputs.baseline_ref }}" in text
    assert "CANDIDATE_REF: ${{ inputs.candidate_ref }}" in text
    assert trust_step < tool_setup < dependency_sync
    assert '"+refs/heads/main:refs/remotes/origin/main"' in text
    assert 'git rev-parse --verify --end-of-options "${BASELINE_REF}^{commit}"' in text
    assert 'git merge-base --is-ancestor "$candidate_sha" origin/main' in text
    assert 'git merge-base --is-ancestor "$baseline_sha" origin/main' in text
    assert 'git merge-base --is-ancestor "$baseline_sha" "$candidate_sha"' in text
    assert "baseline_ref must be an ancestor of candidate_ref" in text
    assert 'git worktree add --detach /tmp/aspenops-baseline "$baseline_sha"' in text
    assert 'git worktree add --detach /tmp/aspenops-baseline "$BASELINE_REF"' not in text
    assert "name: performance-evidence-${{ github.run_id }}" in text
    assert "name: performance-evidence-${{ inputs." not in text


def test_licensed_inputs_and_real_filesystem_targets_are_canonicalized() -> None:
    workflow = workflow_text("licensed-aspen-certification.yml")
    gate = Path("scripts/validate_licensed_paths.py").read_text(encoding="utf-8")

    assert "PLAN_PATH: ${{ inputs.plan_path }}" in workflow
    assert "EXPECTED_HEAD_SHA: ${{ inputs.expected_head_sha }}" in workflow
    assert "EXECUTION_APPROVED: ${{ inputs.approve_real_execution }}" in workflow
    assert "plan_path must be one non-empty line" in workflow
    assert "plan_path escapes the repository workspace" in workflow
    assert "git merge-base --is-ancestor $expected origin/main" in workflow
    assert "python scripts/validate_licensed_paths.py" in workflow
    assert '"PLAN_PATH=$($resolved.plan_path)"' in workflow
    assert '"ASPENOPS_STATE_DIR=$($resolved.state_dir)"' in workflow
    assert "GITHUB_WORKSPACE must be absolute" in gate
    assert "Every ASPENOPS_ALLOWED_ROOTS entry must be absolute" in gate
    assert "ASPENOPS_STATE_DIR must be absolute" in gate
    assert "PLAN_PATH resolves outside GITHUB_WORKSPACE" in gate
    assert "ASPENOPS_STATE_DIR resolves outside ASPENOPS_ALLOWED_ROOTS" in gate
    assert "name: licensed-${{ inputs.backend }}-${{ github.run_id }}" in workflow
    assert "name: licensed-${{ inputs.backend }}-${{ inputs.expected_head_sha }}" not in workflow


def test_windows_gates_run_policy_and_documentation_contracts() -> None:
    for name in ("windows-control-plane.yml", "licensed-aspen-certification.yml"):
        text = workflow_text(name)
        assert "tests/test_config_resource_budgets.py" in text
        assert "tests/test_documentation_contracts.py" in text
        assert "tests/test_real_backend_state_policy.py" in text
        assert "tests/test_licensed_path_gate.py" in text


def test_windows_ci_parses_and_executes_bootstrap_contracts() -> None:
    text = workflow_text("windows-control-plane.yml")
    assert "Parse PowerShell bootstrap" in text
    assert "System.Management.Automation.Language.Parser" in text
    assert "scripts/setup_windows.ps1" in text
    assert "PowerShell parser found errors" in text
    assert "powershell-parse.log" in text
    assert "Exercise PowerShell bootstrap helpers" in text
    assert ". ./scripts/setup_windows.ps1 -LibraryMode" in text
    assert "Duplicate dotenv failure leaked a raw secret" in text
    assert "Unbalanced dotenv failure leaked a raw secret" in text
    assert "winget upgrade/install fallback order was not preserved" in text
    assert "PowerShell bootstrap contracts passed" in text
    assert "powershell-contracts.log" in text


def test_windows_bootstrap_is_frozen_fail_closed_and_secret_safe() -> None:
    text = Path("scripts/setup_windows.ps1").read_text(encoding="utf-8")
    assert "[switch]$LibraryMode" in text
    assert "if (-not $LibraryMode)" in text
    assert "Set-StrictMode -Version Latest" in text
    assert '$RequiredUvVersion = [version]"0.11.16"' in text
    assert "Get-UvVersion" in text
    assert "Try-UvSelfUpdate" in text
    assert "uv self update" in text
    assert '$env:UV_NO_MODIFY_PATH = "1"' in text
    assert 'Invoke-WingetUv -Verb "upgrade"' in text
    assert 'Invoke-WingetUv -Verb "install"' in text
    assert "--accept-package-agreements" in text
    assert "--accept-source-agreements" in text
    assert "Refresh-ProcessPath" in text
    assert "$currentPath = $env:Path" in text
    assert "@($machinePath, $userPath, $currentPath)" in text
    assert "uv lock --check" in text
    assert "uv sync --frozen --extra windows --extra agent --extra dev --extra signing" in text
    assert "Import-DotEnv -Path .env" in text
    assert text.index("Import-DotEnv -Path .env") < text.index("aspenops doctor --probe")
    assert "Invalid .env entry: $entry" not in text
    assert "Invalid .env entry at line $lineNumber" in text
    assert "Duplicate environment variable at line $lineNumber" in text
    assert "Unbalanced quoted value at line $lineNumber" in text
    assert "if ($LASTEXITCODE -ne 0)" in text
