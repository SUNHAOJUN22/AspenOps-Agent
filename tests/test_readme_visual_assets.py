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
    "<foreignobject",
    "<image",
    "javascript:",
    "data:",
    "@import",
    "url(http",
    "url(//",
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
    asset_root = ASSET_DIR.resolve()
    for name in sorted(EXPECTED):
        path = ASSET_DIR / name
        assert path.is_file()
        assert not path.is_symlink()
        assert path.resolve().parent == asset_root
        assert path.stat().st_size <= MAX_SVG_BYTES

        raw = path.read_text(encoding="utf-8")
        folded = raw.casefold()
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
