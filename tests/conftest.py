from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets" / "readme"
DESIGN_SYSTEM = ROOT / "design-system" / "aspenops-readme"
MASTER = DESIGN_SYSTEM / "MASTER.md"
README_OVERRIDE = DESIGN_SYSTEM / "pages" / "readme-visuals.md"
SVG_FONT_SHORTHAND = re.compile(r"(?<![-\w])font\s*:")


@pytest.fixture(scope="session", autouse=True)
def enforce_readme_visual_system_v3() -> None:
    """Keep the persisted design system and all README SVGs on the governed V3 contract."""

    master = MASTER.read_text(encoding="utf-8")
    override = README_OVERRIDE.read_text(encoding="utf-8")
    for marker in (
        "Visual system version: `3`",
        "Product match: `Developer Tool / IDE`",
        "Dark Mode (OLED) + Minimalism",
        'data-design-system="ui-ux-pro-max"',
        'data-visual-version="3"',
    ):
        assert marker in master

    for marker in (
        "23 README",
        "Required implementation markers",
        "render every SVG at 720 × 360",
        "retry_wait",
        "dead_letter",
        "Plan Requirements",
        "Manifest Identity",
        "Fail Before Mutation",
    ):
        assert marker in override

    assets = sorted(ASSET_DIR.glob("*.svg"))
    assert len(assets) == 23
    for path in assets:
        raw = path.read_text(encoding="utf-8")
        root = ET.fromstring(raw)
        assert root.attrib.get("viewBox") == "0 0 1440 720", path.name
        assert root.attrib.get("data-design-system") == "ui-ux-pro-max", path.name
        assert root.attrib.get("data-visual-version") == "3", path.name
        assert SVG_FONT_SHORTHAND.search(raw) is None, path.name
        assert "strokke=" not in raw, path.name
