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
PINNED_ACTION = re.compile(
    r"^\s*-\s+uses:\s+[^@\s]+@([0-9a-f]{40})(?:\s+#.*)?$",
)


def workflow_text(name: str) -> str:
    return (WORKFLOW_DIR / name).read_text(encoding="utf-8")


def shell_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)run:\s*\|\s*$", lines[index])
        if match is None:
            index += 1
            continue
        parent_indent = len(match.group(1))
        block: list[str] = []
        index += 1
        while index < len(lines):
            line = lines[index]
            indent = len(line) - len(line.lstrip())
            if line.strip() and indent <= parent_indent:
                break
            block.append(line)
            index += 1
        blocks.append("\n".join(block))
    return blocks


def test_only_authoritative_long_lived_workflows_exist() -> None:
    observed = {path.name for path in WORKFLOW_DIR.glob("*.yml")}
    observed.update(path.name for path in WORKFLOW_DIR.glob("*.yaml"))
    assert observed == WORKFLOWS


def test_all_external_actions_are_pinned_to_full_commit_shas() -> None:
    for name in WORKFLOWS:
        uses_lines = [
            line for line in workflow_text(name).splitlines() if line.strip().startswith("uses:")
        ]
        assert uses_lines, f"{name} has no external action declarations"
        for line in uses_lines:
            match = PINNED_ACTION.fullmatch(line)
            assert match is not None, f"Unpinned action in {name}: {line.strip()}"


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


def test_dispatch_inputs_never_interpolate_directly_into_shell_blocks() -> None:
    for name in WORKFLOWS:
        for block in shell_blocks(workflow_text(name)):
            assert "${{ inputs." not in block, f"Direct input interpolation in {name} shell block"


def test_manual_workflows_pass_inputs_through_environment_and_safe_artifact_names() -> None:
    performance = workflow_text("generate-performance-evidence.yml")
    assert "BASELINE_REF: ${{ inputs.baseline_ref }}" in performance
    assert "CANDIDATE_REF: ${{ inputs.candidate_ref }}" in performance
    assert "name: performance-evidence-${{ github.run_id }}" in performance
    assert "name: performance-evidence-${{ inputs." not in performance

    licensed = workflow_text("licensed-aspen-certification.yml")
    assert "PLAN_PATH: ${{ inputs.plan_path }}" in licensed
    assert "EXPECTED_HEAD_SHA: ${{ inputs.expected_head_sha }}" in licensed
    assert "EXECUTION_APPROVED: ${{ inputs.approve_real_execution }}" in licensed
    assert "name: licensed-${{ inputs.backend }}-${{ github.run_id }}" in licensed
    assert "name: licensed-${{ inputs.backend }}-${{ inputs.expected_head_sha }}" not in licensed


def test_windows_bootstrap_is_frozen_fail_closed_and_loads_dotenv() -> None:
    text = Path("scripts/setup_windows.ps1").read_text(encoding="utf-8")
    assert "Set-StrictMode -Version Latest" in text
    assert "--accept-package-agreements --accept-source-agreements" in text
    assert "Refresh-ProcessPath" in text
    assert "uv lock --check" in text
    assert "uv sync --frozen --extra windows --extra agent --extra dev --extra signing" in text
    assert "Import-DotEnv -Path .env" in text
    assert text.index("Import-DotEnv -Path .env") < text.index("aspenops doctor --probe")
    assert "if ($LASTEXITCODE -ne 0)" in text
