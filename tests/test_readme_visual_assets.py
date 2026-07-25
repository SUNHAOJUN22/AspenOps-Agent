from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets" / "readme"
MAX_SVG_BYTES = 64_000
EXPECTED = {
    "agent-pipeline.svg",
    "backend-capabilities.svg",
    "cli-mcp-workflow.svg",
    "com-isolation.svg",
    "evidence-chain.svg",
    "hero-architecture.svg",
    "industrial-scenarios.svg",
    "licensed-certification.svg",
    "process-intent-ir.svg",
    "roadmap.svg",
    "scheduler-lifecycle.svg",
    "test-matrix.svg",
}
IMAGE_LINK = re.compile(r"!\[[^\]]*\]\((docs/assets/readme/[^)]+\.svg)\)")
CJK_TEXT = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
SHELL_PLACEHOLDER = re.compile(r"(?m)^uv run aspenops .*<[^>]+>")
FORBIDDEN = (
    "<script",
    "<foreignobject",
    "<image",
    "javascript:",
    "data:",
    "@import",
    "url(http",
    "url(//",
    "noto sans cjk",
    "microsoft yahei",
    "simsun",
    "simhei",
)
WORKFLOW_DIR = ROOT / ".github" / "workflows"
GOVERNED_WORKFLOWS = (
    "ci.yml",
    "windows-control-plane.yml",
    "licensed-aspen-certification.yml",
)
README_CONTRACTS = {
    "README.md": (
        "## 快速开始",
        "## 配置边界",
        "## 典型工作流",
        "## 调度与恢复",
        "## 工业应用场景",
        "## 项目结构",
        "## 故障排查",
        "git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git",
        "uv sync --frozen --extra dev --extra agent --extra signing",
        "uv run aspenops doctor --probe",
        "uv run aspenops run-batch",
        "JOB_ID=$(",
        "uv run aspenops submit",
        "uv run aspenops job",
        "uv run aspenops optimize examples/optimization-request.example.json",
        "uv run aspenops verify-bundle",
        "uv run aspenops mcp",
    ),
    "README.en.md": (
        "## Quick start",
        "## Configuration boundaries",
        "## Common workflows",
        "## Scheduling and recovery",
        "## Industrial use cases",
        "## Repository structure",
        "## Troubleshooting",
        "git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git",
        "uv sync --frozen --extra dev --extra agent --extra signing",
        "uv run aspenops doctor --probe",
        "uv run aspenops run-batch",
        "JOB_ID=$(",
        "uv run aspenops submit",
        "uv run aspenops job",
        "uv run aspenops optimize examples/optimization-request.example.json",
        "uv run aspenops verify-bundle",
        "uv run aspenops mcp",
    ),
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def test_readme_visual_asset_inventory_is_complete_and_referenced() -> None:
    actual = {path.name for path in ASSET_DIR.glob("*.svg")}
    assert actual == EXPECTED

    expected_paths = {f"docs/assets/readme/{name}" for name in EXPECTED}
    for readme in (ROOT / "README.md", ROOT / "README.en.md"):
        text = readme.read_text(encoding="utf-8")
        assert "AI" in text
        assert set(IMAGE_LINK.findall(text)) == expected_paths


def test_readme_svgs_are_self_contained_safe_accessible_and_portable() -> None:
    asset_root = ASSET_DIR.resolve()
    for name in sorted(EXPECTED):
        path = ASSET_DIR / name
        assert path.is_file()
        assert not path.is_symlink()
        assert path.resolve().parent == asset_root
        assert path.stat().st_size <= MAX_SVG_BYTES

        raw = path.read_text(encoding="utf-8")
        folded = raw.casefold()
        assert CJK_TEXT.search(raw) is None, f"{name} contains renderer-dependent CJK text"
        for token in FORBIDDEN:
            assert token not in folded, f"{name} contains forbidden token {token}"

        root = ET.fromstring(raw)
        assert _local_name(root.tag) == "svg"
        assert root.attrib.get("viewBox")
        assert root.attrib.get("role") == "img"

        titles = [child for child in root if _local_name(child.tag) == "title"]
        descriptions = [child for child in root if _local_name(child.tag) == "desc"]
        assert len(titles) == 1 and (titles[0].text or "").strip()
        assert len(descriptions) == 1 and (descriptions[0].text or "").strip()

        labelled_by = set((root.attrib.get("aria-labelledby") or "").split())
        assert titles[0].attrib.get("id") in labelled_by
        assert descriptions[0].attrib.get("id") in labelled_by

        for element in root.iter():
            element_name = _local_name(element.tag).casefold()
            assert element_name not in {"script", "foreignobject", "image"}
            for key, value in element.attrib.items():
                local_key = _local_name(key).casefold()
                assert not local_key.startswith("on")
                if local_key in {"href", "src"}:
                    assert not value.casefold().startswith(
                        ("http:", "https:", "//", "data:", "javascript:")
                    )


def test_readmes_keep_operational_product_surface_complete() -> None:
    for filename, markers in README_CONTRACTS.items():
        text = (ROOT / filename).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text, f"{filename} is missing {marker}"
        assert SHELL_PLACEHOLDER.search(text) is None


def test_visual_asset_governance_remains_in_all_software_gates() -> None:
    marker = "tests/test_readme_visual_assets.py"
    for workflow in GOVERNED_WORKFLOWS:
        text = (WORKFLOW_DIR / workflow).read_text(encoding="utf-8")
        assert marker in text
