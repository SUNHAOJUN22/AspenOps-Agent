#!/usr/bin/env python3
"""Fail-closed Unicode audit for a repository's tracked text files."""

from __future__ import annotations

import argparse
import json
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "six-repository-unicode-integrity/v4"
TEXT_EXTENSIONS = frozenset(
    {
        ".cfg",
        ".cjs",
        ".css",
        ".csv",
        ".html",
        ".ini",
        ".js",
        ".jsx",
        ".json",
        ".jsonl",
        ".md",
        ".mdx",
        ".mjs",
        ".ps1",
        ".py",
        ".pyi",
        ".scss",
        ".sh",
        ".sql",
        ".svg",
        ".toml",
        ".ts",
        ".tsx",
        ".tsv",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
)
EXCLUDED_PARTS = frozenset(
    {
        ".git",
        ".hypothesis",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "artifacts",
        "build",
        "dist",
        "node_modules",
        "site",
    }
)


def _token(*codepoints: int) -> str:
    return "".join(chr(value) for value in codepoints)


def mojibake_markers() -> tuple[tuple[str, str], ...]:
    """Construct suspect tokens without embedding corrupt text in source."""

    return (
        ("latin1-replacement", _token(0x00EF, 0x00BF, 0x00BD)),
        ("smart-apostrophe", _token(0x00E2, 0x20AC, 0x2122)),
        ("smart-double-quote", _token(0x00E2, 0x20AC, 0x0153)),
        ("utf8-cjk-wen", _token(0x00E6, 0x2013, 0x2021)),
        ("utf8-cjk-zhong", _token(0x00E4, 0x00B8, 0x00AD)),
        ("utf8-cjk-tu", _token(0x00E5, 0x203A, 0x00BE)),
        ("gbk-replacement", _token(0x951F, 0x65A4, 0x62F7)),
        ("debug-fill-hot", _token(0x70EB, 0x70EB, 0x70EB)),
        ("debug-fill-tun", _token(0x5C6F, 0x5C6F, 0x5C6F)),
    )


def tracked_text_paths(root: Path) -> list[Path]:
    """Return deterministic tracked text paths, never generated directories."""

    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
        timeout=60,
    )
    selected: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8", errors="strict"))
        if any(
            part in EXCLUDED_PARTS or part.endswith(".egg-info")
            for part in relative.parts
        ):
            continue
        if relative.suffix.casefold() not in TEXT_EXTENSIONS:
            continue
        selected.append(root / relative)
    return sorted(selected, key=lambda path: path.relative_to(root).as_posix())


def audit_paths(root: Path, paths: Iterable[Path]) -> dict[str, Any]:
    """Audit explicit paths so the contract is unit-testable without Git."""

    root = root.resolve()
    failures: list[dict[str, str]] = []
    scanned = 0
    for path in paths:
        scanned += 1
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            failures.append(
                {"category": "unsafe_path", "path": str(path), "detail": "escapes root"}
            )
            continue
        if path.is_symlink() or not path.is_file():
            failures.append(
                {
                    "category": "unsafe_path",
                    "path": relative,
                    "detail": "not a regular file",
                }
            )
            continue
        data = path.read_bytes()
        if data.startswith(b"\xef\xbb\xbf"):
            failures.append(
                {"category": "bom", "path": relative, "detail": "UTF-8 BOM"}
            )
        if b"\r" in data:
            failures.append(
                {"category": "line_endings", "path": relative, "detail": "CR or CRLF"}
            )
        if not data.endswith(b"\n"):
            failures.append(
                {"category": "terminal_lf", "path": relative, "detail": "missing LF"}
            )
        elif data.endswith(b"\n\n"):
            failures.append(
                {
                    "category": "terminal_lf",
                    "path": relative,
                    "detail": "more than one terminal LF",
                }
            )
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            failures.append(
                {
                    "category": "invalid_utf8",
                    "path": relative,
                    "detail": f"byte {exc.start}",
                }
            )
            continue
        if chr(0xFFFD) in text:
            failures.append(
                {"category": "replacement_character", "path": relative, "detail": "U+FFFD"}
            )
        if unicodedata.normalize("NFC", text) != text:
            failures.append(
                {"category": "nfc", "path": relative, "detail": "not NFC"}
            )
        controls = sorted(
            {
                f"U+{ord(character):04X}"
                for character in text
                if unicodedata.category(character) == "Cc"
                and character not in {"\n", "\t"}
            }
        )
        if controls:
            failures.append(
                {
                    "category": "control_character",
                    "path": relative,
                    "detail": ", ".join(controls),
                }
            )
        markers = [name for name, marker in mojibake_markers() if marker in text]
        if markers:
            failures.append(
                {
                    "category": "mojibake",
                    "path": relative,
                    "detail": ", ".join(markers),
                }
            )
    failures.sort(key=lambda item: (item["path"], item["category"], item["detail"]))
    return {
        "schema_version": SCHEMA,
        "verdict": "PASS" if not failures else "FAIL",
        "scanned_text_files": scanned,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    report = audit_paths(root, tracked_text_paths(root))
    rendered = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
