from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets" / "readme"
ARCHITECTURE = ROOT / "docs" / "architecture.md"
MAX_SVG_BYTES = 64_000
EXPECTED = {
    "agent-pipeline.svg",
    "backend-capabilities.svg",
    "cache-singleflight.svg",
    "cli-mcp-workflow.svg",
    "com-isolation.svg",
    "durable-path-portability.svg",
    "evidence-chain.svg",
    "hero-architecture.svg",
    "industrial-scenarios.svg",
    "licensed-certification.svg",
    "mcp-runtime-lifecycle.svg",
    "optimization-lifecycle.svg",
    "policy-path-safety.svg",
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
        "## 配置与路径安全策略",
        "## 典型工作流",
        "## MCP 兼容性与服务生命周期",
        "## 约束优化闭环",
        "## 调度与恢复",
        "## 缓存、批内去重与单航班",
        "## 工业应用场景",
        "## 项目结构",
        "## 故障排查",
        "git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git",
        "uv sync --frozen --extra dev --extra agent --extra signing",
        "mcp>=1.9,<2",
        "uv run aspenops doctor --probe",
        "uv run aspenops run-batch",
        "uv run aspenops scheduler",
        "JOB_ID=$(",
        "uv run aspenops submit",
        "uv run aspenops job",
        "uv run aspenops cancel",
        "uv run aspenops optimize examples/optimization-request.example.json",
        "uv run aspenops verify-bundle",
        "uv run aspenops mcp",
        "paths_pinned",
        "submission_cwd",
        "retry_wait",
        "dead_letter",
        "inflight_singleflight",
        "PENDING_REAL_ASPEN_CERTIFICATION",
    ),
    "README.en.md": (
        "## Quick start",
        "## Configuration boundaries",
        "## Configuration and path safety",
        "## Common workflows",
        "## MCP compatibility and server lifecycle",
        "## Constrained optimization lifecycle",
        "## Scheduling and recovery",
        "## Cache, batch deduplication and singleflight",
        "## Industrial use cases",
        "## Repository structure",
        "## Troubleshooting",
        "git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git",
        "uv sync --frozen --extra dev --extra agent --extra signing",
        "mcp>=1.9,<2",
        "uv run aspenops doctor --probe",
        "uv run aspenops run-batch",
        "uv run aspenops scheduler",
        "JOB_ID=$(",
        "uv run aspenops submit",
        "uv run aspenops job",
        "uv run aspenops cancel",
        "uv run aspenops optimize examples/optimization-request.example.json",
        "uv run aspenops verify-bundle",
        "uv run aspenops mcp",
        "paths_pinned",
        "submission_cwd",
        "retry_wait",
        "dead_letter",
        "inflight_singleflight",
        "PENDING_REAL_ASPEN_CERTIFICATION",
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
        assert "seventeen" in text.casefold() or "十七" in text


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


def test_new_visuals_remain_bound_to_implemented_runtime_contracts() -> None:
    config = (ROOT / "src/aspenops_nexus/config.py").read_text(encoding="utf-8")
    optimization = (ROOT / "src/aspenops_nexus/optimization.py").read_text(encoding="utf-8")
    pool = (ROOT / "src/aspenops_nexus/pool.py").read_text(encoding="utf-8")
    cache = (ROOT / "src/aspenops_nexus/cache.py").read_text(encoding="utf-8")

    policy_visual = (ASSET_DIR / "policy-path-safety.svg").read_text(encoding="utf-8")
    optimization_visual = (ASSET_DIR / "optimization-lifecycle.svg").read_text(
        encoding="utf-8"
    )
    cache_visual = (ASSET_DIR / "cache-singleflight.svg").read_text(encoding="utf-8")

    for marker in ("_SUPPORTED_BACKENDS", "_require_bool", "allowed_roots"):
        assert marker in config
    for marker in ("Python Settings", "Canonical Paths", "Operation Gates"):
        assert marker in policy_visual

    for marker in (
        "OptimizationBudget",
        "differential_evolution_batch",
        "checkpoint_path",
        "PENDING_REAL_ASPEN_CERTIFICATION",
    ):
        assert marker in optimization
    for marker in ("Budget Gate", "Atomic Checkpoint", "Pareto Front"):
        assert marker in optimization_visual

    for marker in ("_InflightEvaluation", "inflight_singleflight", "same_batch_dedup"):
        assert marker in pool
    for marker in ("PRAGMA journal_mode=WAL", "_MEMORY_MAX_ENTRIES"):
        assert marker in cache
    for marker in ("Memory LRU", "SQLite WAL", "singleflight"):
        assert marker in cache_visual


def test_readmes_keep_operational_product_surface_complete() -> None:
    for filename, markers in README_CONTRACTS.items():
        text = (ROOT / filename).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text, f"{filename} is missing {marker}"
        assert SHELL_PLACEHOLDER.search(text) is None


def test_scheduler_documents_match_recovery_state_machine() -> None:
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    visual = (ASSET_DIR / "scheduler-lifecycle.svg").read_text(encoding="utf-8")
    for text in (architecture, visual):
        assert "retry_wait" in text
        assert "dead_letter" in text
    assert "moved to `interrupted`" not in architecture
    assert "restart → interrupted state" not in visual


def test_visual_asset_governance_remains_in_all_software_gates() -> None:
    marker = "tests/test_readme_visual_assets.py"
    for workflow in GOVERNED_WORKFLOWS:
        text = (WORKFLOW_DIR / workflow).read_text(encoding="utf-8")
        assert marker in text
