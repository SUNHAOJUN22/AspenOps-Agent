"""Check the current native-AI figure contract without rewriting qualification claims.

This legacy command used to insert a deterministic SVG atlas and copy historical
qualification counts into the READMEs. Current figures are authored in context;
this entry point now validates them without modifying prose, images or evidence.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ("architecture.png", "algorithm.png", "roadmap.png", "seven-repo-roadmap.png")
DOCUMENT_FIGURES = {
    "README.md": tuple(f"docs/assets/ai-generated/{name}" for name in FIGURES),
    "README.en.md": tuple(f"docs/assets/ai-generated/{name}" for name in FIGURES),
    "README_ACCEPTANCE.md": ("docs/assets/ai-generated/roadmap.png",),
    "docs/assets/README.md": tuple(f"ai-generated/{name}" for name in FIGURES),
}
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
HTML_IMAGE = re.compile(r"<\s*(?:img|picture|source|object|embed|iframe|svg)\b", re.I)
BADGE_PREFIX = "https://img.shields.io/badge/"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def check_current_figures(root: Path) -> list[str]:
    """Return actionable issues; never edit documentation or qualification data."""
    issues: list[str] = []
    for relative, expected in DOCUMENT_FIGURES.items():
        document = root / relative
        if not document.is_file():
            issues.append(f"{relative}: missing document")
            continue
        text = document.read_text(encoding="utf-8")
        images = IMAGE.findall(text)
        figures = [target for target in images if not target.startswith(BADGE_PREFIX)]
        if set(figures) != set(expected) or len(figures) != len(expected):
            issues.append(f"{relative}: embed each current native PNG exactly once: {expected}")
        if text.count("![") != len(images) or HTML_IMAGE.search(text):
            issues.append(f"{relative}: use explicit Markdown image links only")
        for target in expected:
            asset = document.parent / target
            if asset.is_symlink() or not asset.is_file():
                issues.append(f"{relative}: missing or symlinked asset: {target}")
            else:
                with asset.open("rb") as stream:
                    if stream.read(len(PNG_MAGIC)) != PNG_MAGIC:
                        issues.append(f"{relative}: asset is not a PNG: {target}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check native AI README figures; never rewrite qualification claims"
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="Check only (the default)")
    args = parser.parse_args()
    issues = check_current_figures(args.root.resolve())
    if issues:
        for issue in issues:
            print(issue)
        return 1
    print("PASS: four native AI figures, localized entry points and acceptance route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
