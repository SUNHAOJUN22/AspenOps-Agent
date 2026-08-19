#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import io
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / ".tsao-skill-native-v17"
EXPECTED_BLOB_SHA = "66dbdedbc04025cbbf0d46bfb4c89d7581804474"
TEXT_SUFFIXES = {
    ".cfg", ".css", ".html", ".ini", ".js", ".json", ".md", ".mjs", ".py",
    ".svg", ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
}
REMOVE = [
    ".github/V15_FINAL_QUALIFICATION.md",
    "V15_RELEASE_NOTES.md",
    ".github/workflows/apply-skill-native-v15-fix1.yml",
    ".github/workflows/apply-skill-native-v15-fix2.yml",
    ".github/workflows/branch-hygiene-v15.yml",
    "scripts/apply_skill_native_v15_fix1.py",
    "scripts/apply_skill_native_v15_fix2.py",
    ".github/workflows/tsao-remediation-v14.yml",
    ".tsao-remediation-v14",
    "src/aspenops_nexus/scientific_contracts_v16.py",
    "tests/test_scientific_contracts_v16.py",
]
ROOT_READMES = {"README.md", "README.en.md", "README.zh-CN.md", "README_CN.md"}
START = "<!-- TSAO_SKILL_NATIVE_V17_START -->"
END = "<!-- TSAO_SKILL_NATIVE_V17_END -->"
OLD = re.compile(
    r"<!-- TSAO_SKILL_NATIVE_V(?:1[0-6]|[1-9])_START -->.*?"
    r"<!-- TSAO_SKILL_NATIVE_V(?:1[0-6]|[1-9])_END -->\s*",
    re.S,
)


def safe_extract(tf: tarfile.TarFile, target: Path) -> None:
    root = target.resolve()
    for member in tf.getmembers():
        dest = (target / member.name).resolve()
        if root not in dest.parents and dest != root:
            raise RuntimeError(f"unsafe archive member: {member.name}")
        if member.issym() or member.islnk():
            raise RuntimeError(f"links are forbidden: {member.name}")
    tf.extractall(target, filter="data")


def locate_payload_root(extracted: Path) -> Path:
    if (extracted / "files").is_dir():
        return extracted
    candidates = sorted(
        {files_dir.parent.resolve() for files_dir in extracted.rglob("files") if files_dir.is_dir()}
    )
    if len(candidates) != 1:
        raise RuntimeError(
            "payload layout invalid: expected exactly one files/ root, "
            f"found {len(candidates)}: {[candidate.as_posix() for candidate in candidates[:20]]}"
        )
    return candidates[0]


def load_apply(path: Path):
    name = "tsao_v17_" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    fn = getattr(mod, "apply", None)
    if not callable(fn):
        raise RuntimeError(f"no apply(root) in {path}")
    return fn


def language(path: Path, text: str) -> str:
    if path.name == "README.en.md":
        return "en"
    if path.name in {"README.zh-CN.md", "README_CN.md"}:
        return "zh"
    count = sum(1 for char in text if "\u3400" <= char <= "\u9fff")
    return "zh" if count >= 40 else "en"


def merge(text: str, section: str) -> str:
    text = OLD.sub("", text).rstrip()
    return text + "\n\n" + START + "\n" + section.rstrip() + "\n" + END + "\n"


def verify_tracked_payload(payload_file: Path) -> None:
    actual = subprocess.check_output(
        ["git", "hash-object", payload_file.relative_to(ROOT).as_posix()],
        cwd=ROOT,
        text=True,
    ).strip()
    if actual != EXPECTED_BLOB_SHA:
        raise RuntimeError(
            f"payload Git blob mismatch: expected {EXPECTED_BLOB_SHA}, observed {actual}"
        )


def copy_verified(source: Path, dest: Path, rel: Path) -> None:
    raw = source.read_bytes()
    if source.suffix.lower() in TEXT_SUFFIXES or source.name in {"SKILL.md", "README"}:
        if b"\x00" in raw:
            raise RuntimeError(f"NUL byte in text payload: {rel.as_posix()}")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"non-UTF-8 text payload: {rel.as_posix()}: {exc}") from exc
        if "\ufffd" in text:
            raise RuntimeError(f"replacement character in text payload: {rel.as_posix()}")
        dest.write_text(text, encoding="utf-8", newline="\n")
    else:
        shutil.copy2(source, dest)


def main() -> int:
    payload_file = PAYLOAD / "payload.tar.gz"
    if not payload_file.is_file():
        raise RuntimeError("payload file missing")
    verify_tracked_payload(payload_file)
    raw = payload_file.read_bytes()
    with tempfile.TemporaryDirectory(prefix="tsao-v17-") as tmp:
        extracted = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
            safe_extract(tf, extracted)
        payload_root = locate_payload_root(extracted)
        files = payload_root / "files"
        section_en = payload_root / "readme_sections/section-en.md"
        section_zh = payload_root / "readme_sections/section-zh.md"
        has_sections = section_en.is_file() and section_zh.is_file()
        for source in sorted(files.rglob("*")):
            if not source.is_file():
                continue
            rel = source.relative_to(files)
            if rel.parts and rel.parts[0] == "artifacts":
                continue
            if len(rel.parts) >= 2 and rel.parts[:2] == (".github", "workflows"):
                continue
            if has_sections and len(rel.parts) == 1 and rel.name in ROOT_READMES:
                continue
            dest = ROOT / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            copy_verified(source, dest, rel)
        if has_sections:
            sections = {
                "en": section_en.read_text(encoding="utf-8"),
                "zh": section_zh.read_text(encoding="utf-8"),
            }
            candidates = [
                ROOT / name
                for name in ("README.md", "README.en.md", "README.zh-CN.md", "README_CN.md")
            ]
            existing = [path for path in candidates if path.is_file()]
            assigned = [(path, language(path, path.read_text(encoding="utf-8"))) for path in existing]
            langs = {lang for _, lang in assigned}
            if "en" not in langs:
                path = ROOT / (
                    "README.md" if not (ROOT / "README.md").exists() else "README.en.md"
                )
                path.write_text("# AspenOps-Agent\n", encoding="utf-8")
                assigned.append((path, "en"))
            if "zh" not in langs:
                path = ROOT / "README.zh-CN.md"
                path.write_text("# AspenOps-Agent\n", encoding="utf-8")
                assigned.append((path, "zh"))
            seen: set[Path] = set()
            for path, lang in assigned:
                if path in seen:
                    continue
                seen.add(path)
                path.write_text(
                    merge(path.read_text(encoding="utf-8"), sections[lang]),
                    encoding="utf-8",
                    newline="\n",
                )
        transforms = payload_root / "transforms"
        if transforms.is_dir():
            for path in sorted(transforms.glob("*.py")):
                load_apply(path)(ROOT)
    for rel in REMOVE:
        target = ROOT / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    print("V17 deterministic application complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
