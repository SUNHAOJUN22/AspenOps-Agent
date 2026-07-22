from __future__ import annotations

import re
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CURRENT_UV_VERSION = "0.11.16"
WORKFLOWS = {
    "ci.yml",
    "generate-performance-evidence.yml",
    "licensed-aspen-certification.yml",
    "windows-control-plane.yml",
}
PRIMARY_DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "README.en.md",
    ROOT / "AGENTS.md",
    ROOT / "CLAUDE.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "CHANGELOG.md",
    ROOT / "SECURITY.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "performance.md",
    ROOT / "docs" / "windows-setup.md",
    ROOT / "docs" / "quality-report.md",
    ROOT / "docs" / "automated-test-audit-2026-07-22.md",
    ROOT / "docs" / "certification.md",
)
HISTORICAL_DOCUMENTS = {
    ROOT / "CHANGELOG.md",
    ROOT / "docs" / "automated-test-audit-2026-07-22.md",
}
CURRENT_GUIDES = tuple(
    document for document in PRIMARY_DOCUMENTS if document not in HISTORICAL_DOCUMENTS
)
UNIVERSAL_STALE_TOKENS = {
    "ubuntu-latest",
    "windows-latest",
    "windows-aspen-certification.yml",
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _project_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _local_link_target(document: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    else:
        target = target.split(maxsplit=1)[0]

    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith("#"):
        return None
    if not parsed.path:
        return None

    candidate = (document.parent / unquote(parsed.path)).resolve()
    if candidate != ROOT and ROOT not in candidate.parents:
        raise AssertionError(f"Documentation link escapes repository: {document}: {target}")
    return candidate


def test_primary_documentation_exists_and_local_links_resolve() -> None:
    for document in PRIMARY_DOCUMENTS:
        assert document.is_file(), f"Missing documentation file: {document.relative_to(ROOT)}"
        text = document.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            candidate = _local_link_target(document, raw_target)
            if candidate is not None:
                assert candidate.exists(), (
                    f"Broken local link in {document.relative_to(ROOT)}: "
                    f"{candidate.relative_to(ROOT)}"
                )


def test_package_and_documentation_versions_match() -> None:
    version = _project_version()
    major_minor = ".".join(version.split(".")[:2])
    chinese = (ROOT / "README.md").read_text(encoding="utf-8")
    english = (ROOT / "README.en.md").read_text(encoding="utf-8")
    package_init = (ROOT / "src" / "aspenops_nexus" / "__init__.py").read_text(
        encoding="utf-8"
    )
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    for readme in (chinese, english):
        assert f"# AspenOps {major_minor}" in readme
        assert f"version-{version}-" in readme
        assert f"aspenops-nexus {version}" in readme
    assert f'__version__ = "{version}"' in package_init
    assert f"## {version} -" in changelog
    assert (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8").startswith(
        f"# AspenOps {major_minor} Architecture"
    )
    assert (ROOT / "AGENTS.md").read_text(encoding="utf-8").startswith(
        f"# AspenOps {major_minor} Agent Contract"
    )
    assert (ROOT / "CLAUDE.md").read_text(encoding="utf-8").startswith(
        f"# Claude Code operating contract for AspenOps {major_minor}"
    )
    assert (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").startswith(
        f"# Contributing to AspenOps {major_minor}"
    )


def test_documentation_has_no_stale_current_guidance() -> None:
    for document in PRIMARY_DOCUMENTS:
        text = document.read_text(encoding="utf-8")
        for token in UNIVERSAL_STALE_TOKENS:
            assert token not in text, f"Stale token {token!r} in {document.relative_to(ROOT)}"

    for document in CURRENT_GUIDES:
        text = document.read_text(encoding="utf-8")
        assert "0.11.14" not in text, f"Stale uv guidance in {document.relative_to(ROOT)}"
        assert "AspenOps 1.0" not in text, (
            f"Stale product title in {document.relative_to(ROOT)}"
        )

    readmes = [
        (ROOT / "README.md").read_text(encoding="utf-8"),
        (ROOT / "README.en.md").read_text(encoding="utf-8"),
    ]
    for text in readmes:
        assert CURRENT_UV_VERSION in text
        assert "ubuntu-24.04" in text
        assert "windows-2025" in text
        for workflow in WORKFLOWS:
            assert workflow in text


def test_operational_guides_require_frozen_quality_gates() -> None:
    for document in (ROOT / "AGENTS.md", ROOT / "CONTRIBUTING.md"):
        text = document.read_text(encoding="utf-8")
        assert "uv lock --check" in text
        assert "uv sync --frozen" in text
        assert "uv sync --extra" not in text
        assert "uv run ruff check ." in text
        assert "uv run ruff format --check ." in text
        assert "uv run mypy src" in text
        assert "--cov-fail-under=94.5" in text


def test_documentation_describes_all_six_dependency_audit_targets() -> None:
    chinese = (ROOT / "README.md").read_text(encoding="utf-8")
    english = (ROOT / "README.en.md").read_text(encoding="utf-8")
    quality = (ROOT / "docs" / "quality-report.md").read_text(encoding="utf-8")
    audit = (ROOT / "docs" / "automated-test-audit-2026-07-22.md").read_text(
        encoding="utf-8"
    )

    assert "Python 3.11、3.12、3.13" in chinese
    assert "Linux 与 Windows" in chinese
    assert "六种" in chinese
    assert "Python 3.11, 3.12 and 3.13" in english
    assert "Linux and Windows" in english
    assert "six" in english.casefold()
    for text in (quality, audit):
        assert "Python 3.11, 3.12 and 3.13" in text
        assert "six" in text.casefold()
        assert "documentation" in text.casefold()


def test_environment_template_keeps_first_run_portable() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ASPENOPS_BACKEND=mock" in text
    assert "ASPENOPS_ALLOWED_ROOTS=\n" in text
    assert "ASPENOPS_STATE_DIR=var/aspenops-state" in text
    assert "# ASPENOPS_BACKEND=aspen_plus" in text
    assert "# ASPENOPS_ALLOWED_ROOTS=C:/AspenModels;C:/AspenResults" in text
    assert "# ASPENOPS_STATE_DIR=C:/AspenResults/aspenops-state" in text


def test_windows_guide_matches_hardened_bootstrap() -> None:
    text = (ROOT / "docs" / "windows-setup.md").read_text(encoding="utf-8")
    assert "automatically upgrades" in text
    assert "self-update" in text
    assert "winget" in text
    assert "duplicate variable" in text.casefold()
    assert "unbalanced" in text.casefold()
    assert "without echoing raw" in text
    assert "test_documentation_contracts.py" in text


def test_readmes_preserve_evidence_and_certification_boundaries() -> None:
    chinese = (ROOT / "README.md").read_text(encoding="utf-8")
    english = (ROOT / "README.en.md").read_text(encoding="utf-8")

    assert "已验证归档基线" in chinese
    assert "不是对任意后续提交的自动声明" in chinese
    assert "PENDING_REAL_ASPEN_CERTIFICATION" in chinese
    assert "archived validated baseline" in english.casefold()
    assert "not an automatic claim" in english.casefold()
    assert "PENDING_REAL_ASPEN_CERTIFICATION" in english
