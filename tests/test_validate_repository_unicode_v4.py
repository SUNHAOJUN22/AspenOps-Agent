from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = runpy.run_path(str(ROOT / "scripts" / "validate_repository_unicode_v4.py"))
audit_paths = NAMESPACE["audit_paths"]


def test_clean_unicode_text_passes(tmp_path: Path) -> None:
    path = tmp_path / "clean.md"
    path.write_text("安全 scientific text\n", encoding="utf-8", newline="\n")

    report = audit_paths(tmp_path, [path])

    assert report["verdict"] == "PASS"
    assert report["scanned_text_files"] == 1


def test_encoding_and_rendering_failures_are_structured(tmp_path: Path) -> None:
    (tmp_path / "bom.md").write_bytes(b"\xef\xbb\xbftext\r\n")
    (tmp_path / "replacement.txt").write_text(
        f"bad {chr(0xFFFD)} text\n", encoding="utf-8", newline="\n"
    )
    mojibake = "".join(chr(value) for value in (0x951F, 0x65A4, 0x62F7))
    (tmp_path / "mojibake.md").write_text(
        f"bad {mojibake} text\n", encoding="utf-8", newline="\n"
    )

    report = audit_paths(tmp_path, sorted(tmp_path.iterdir()))
    categories = {item["category"] for item in report["failures"]}

    assert report["verdict"] == "FAIL"
    assert {"bom", "line_endings", "replacement_character", "mojibake"} <= categories
