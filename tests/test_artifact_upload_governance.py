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
UPLOAD_ACTION = "actions/upload-artifact@"
ARTIFACT_NAME = re.compile(r"^\s*name:\s*(.+)$", re.MULTILINE)


def workflow_text(name: str) -> str:
    return (WORKFLOW_DIR / name).read_text(encoding="utf-8")


def upload_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for chunk in text.split(UPLOAD_ACTION)[1:]:
        blocks.append(chunk.split("\n      - ", 1)[0])
    return blocks


def test_upload_artifacts_are_rerun_safe_and_fail_closed() -> None:
    for workflow in WORKFLOWS:
        blocks = upload_blocks(workflow_text(workflow))
        assert blocks, f"{workflow} has no artifact upload step"
        names: list[str] = []
        for block in blocks:
            assert "${{ github.run_id }}" in block
            assert "${{ github.run_attempt }}" in block
            assert "if-no-files-found: error" in block
            assert "if-no-files-found: ignore" not in block
            assert "if-no-files-found: warn" not in block
            match = ARTIFACT_NAME.search(block)
            assert match is not None, f"Unnamed artifact in {workflow}"
            names.append(match.group(1).strip())
        assert len(names) == len(set(names)), f"Duplicate artifact templates in {workflow}"


def test_matrix_and_specialized_artifact_names_remain_distinct() -> None:
    portable = workflow_text("ci.yml")
    windows = workflow_text("windows-control-plane.yml")
    performance = workflow_text("generate-performance-evidence.yml")
    licensed = workflow_text("licensed-aspen-certification.yml")

    quality = "ci-evidence-quality-${{ github.run_id }}-${{ github.run_attempt }}"
    python = (
        "ci-evidence-python-${{ matrix.python-version }}-"
        "${{ github.run_id }}-${{ github.run_attempt }}"
    )
    windows_name = (
        "windows-control-plane-diagnostics-${{ github.run_id }}-"
        "${{ github.run_attempt }}"
    )
    performance_name = (
        "performance-evidence-${{ github.run_id }}-${{ github.run_attempt }}"
    )
    licensed_name = (
        "licensed-${{ inputs.backend }}-${{ github.run_id }}-"
        "${{ github.run_attempt }}"
    )

    assert quality in portable
    assert python in portable
    assert windows_name in windows
    assert performance_name in performance
    assert licensed_name in licensed


def test_readmes_document_rerun_safe_fail_closed_artifacts() -> None:
    for path in (Path("README.md"), Path("README.en.md")):
        text = path.read_text(encoding="utf-8")
        assert "github.run_id" in text
        assert "github.run_attempt" in text
        assert "if-no-files-found: error" in text
