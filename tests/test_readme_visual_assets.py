from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets" / "readme"
EXPECTED = {
    "agent-pipeline.svg",
    "backend-capabilities.svg",
    "com-isolation.svg",
    "evidence-chain.svg",
    "hero-architecture.svg",
    "licensed-certification.svg",
    "process-intent-ir.svg",
    "roadmap.svg",
    "test-matrix.svg",
}
IMAGE_LINK = re.compile(r"!\[[^\]]*\]\((docs/assets/readme/[^)]+\.svg)\)")
FORBIDDEN = (
    "<script",
    "<foreignObject",
    "javascript:",
    "data:text/html",
    "onload=",
    "onclick=",
    "onerror=",
)


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


def test_readme_svgs_are_self_contained_safe_and_accessible() -> None:
    for name in sorted(EXPECTED):
        path = ASSET_DIR / name
        raw = path.read_text(encoding="utf-8")
        folded = raw.casefold()

        assert len(raw.encode("utf-8")) <= 64_000
        for token in FORBIDDEN:
            assert token.casefold() not in folded, f"{name} contains forbidden token {token}"

        root = ET.fromstring(raw)
        assert _local_name(root.tag) == "svg"
        assert root.attrib.get("viewBox")
        assert root.attrib.get("role") == "img"
        assert root.attrib.get("aria-labelledby") == "title desc"

        children = list(root)
        has_title = any(
            _local_name(child.tag) == "title" and (child.text or "").strip()
            for child in children
        )
        has_desc = any(
            _local_name(child.tag) == "desc" and (child.text or "").strip()
            for child in children
        )
        assert has_title
        assert has_desc

        for element in root.iter():
            for key, value in element.attrib.items():
                local_key = _local_name(key).casefold()
                if local_key in {"href", "src"}:
                    assert not value.startswith(("http:", "https:", "//", "data:"))
                assert not local_key.startswith("on")
