from __future__ import annotations

import re
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
UV_VERSION = "0.11.16"
WORKFLOWS = {
    "ci.yml",
    "generate-performance-evidence.yml",
    "licensed-aspen-certification.yml",
    "windows-control-plane.yml",
}
DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "README.en.md",
    ROOT / "AGENTS.md",
    ROOT / "CLAUDE.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "CHANGELOG.md",
    ROOT / "SECURITY.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "process-intent-ir.md",
    ROOT / "docs" / "external-agent-integration.md",
    ROOT / "docs" / "performance.md",
    ROOT / "docs" / "windows-setup.md",
    ROOT / "docs" / "quality-report.md",
    ROOT / "docs" / "automated-test-audit-2026-07-22.md",
    ROOT / "docs" / "certification.md",
)
HISTORICAL = {
    ROOT / "CHANGELOG.md",
    ROOT / "docs" / "automated-test-audit-2026-07-22.md",
}
STALE_TOKENS = {
    "ubuntu-latest",
    "windows-latest",
    "windows-aspen-certification.yml",
}
CHAT_ONLY_TOKENS = ("cite", "filecite", "sandbox:/")
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _project_version() -> str:
    data = tomllib.loads(_read(ROOT / "pyproject.toml"))
    return str(data["project"]["version"])


def _local_target(document: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    else:
        target = target.split(maxsplit=1)[0]
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith("#") or not parsed.path:
        return None
    candidate = (document.parent / unquote(parsed.path)).resolve()
    if candidate != ROOT and ROOT not in candidate.parents:
        raise AssertionError(f"Documentation link escapes repository: {document}: {target}")
    return candidate


def test_documents_exist_links_resolve_and_chat_markup_is_absent() -> None:
    for document in DOCUMENTS:
        assert document.is_file(), f"Missing documentation file: {document.relative_to(ROOT)}"
        text = _read(document)
        for token in CHAT_ONLY_TOKENS:
            assert token not in text
        for raw_target in MARKDOWN_LINK.findall(text):
            candidate = _local_target(document, raw_target)
            if candidate is not None:
                assert candidate.exists(), f"Broken link in {document}: {raw_target}"


def test_package_and_documentation_versions_match() -> None:
    version = _project_version()
    major_minor = ".".join(version.split(".")[:2])
    readmes = (_read(ROOT / "README.md"), _read(ROOT / "README.en.md"))
    for readme in readmes:
        assert f"# AspenOps {major_minor}" in readme
        assert f"version-{version}-" in readme
        assert f"aspenops-nexus {version}" in readme
    package_init = _read(ROOT / "src" / "aspenops_nexus" / "__init__.py")
    assert f'__version__ = "{version}"' in package_init
    assert f"## {version} -" in _read(ROOT / "CHANGELOG.md")
    assert _read(ROOT / "docs" / "architecture.md").startswith(
        f"# AspenOps {major_minor} Architecture"
    )
    assert _read(ROOT / "AGENTS.md").startswith(
        f"# AspenOps {major_minor} Agent Contract"
    )
    assert _read(ROOT / "CLAUDE.md").startswith(
        f"# Claude Code operating contract for AspenOps {major_minor}"
    )
    assert _read(ROOT / "CONTRIBUTING.md").startswith(
        f"# Contributing to AspenOps {major_minor}"
    )


def test_current_guidance_has_no_stale_toolchain_or_product_names() -> None:
    for document in DOCUMENTS:
        text = _read(document)
        for token in STALE_TOKENS:
            assert token not in text
        if document not in HISTORICAL:
            assert "0.11.14" not in text
            assert "AspenOps 1.0" not in text
    for path in (ROOT / "README.md", ROOT / "README.en.md"):
        text = _read(path)
        assert UV_VERSION in text
        assert "ubuntu-24.04" in text
        assert "windows-2025" in text
        assert WORKFLOWS.issubset(set(re.findall(r"[\w-]+\.yml", text)))


def test_operational_guides_require_frozen_quality_gates() -> None:
    for path in (ROOT / "AGENTS.md", ROOT / "CONTRIBUTING.md"):
        text = _read(path)
        assert "uv lock --check" in text
        assert "uv sync --frozen" in text
        assert "uv sync --extra" not in text
        assert "uv run ruff check ." in text
        assert "uv run ruff format --check ." in text
        assert "uv run mypy src" in text
        assert "--cov-fail-under=94.5" in text


def test_docs_describe_six_audits_and_runner_temp_evidence() -> None:
    chinese = _read(ROOT / "README.md")
    english = _read(ROOT / "README.en.md")
    quality = _read(ROOT / "docs" / "quality-report.md")
    audit = _read(ROOT / "docs" / "automated-test-audit-2026-07-22.md")
    performance = _read(ROOT / "docs" / "performance.md")
    assert "Python 3.11、3.12、3.13" in chinese
    assert "Linux 与 Windows" in chinese
    assert "六种" in chinese or "六组合" in chinese
    assert "Python 3.11, 3.12 and 3.13" in english
    assert "Linux and Windows" in english
    assert "six" in english.casefold()
    for text in (quality, audit):
        assert "Python 3.11, 3.12 and 3.13" in text
        assert "six" in text.casefold()
    for text in (chinese, english, quality, audit, performance):
        assert "RUNNER_TEMP" in text
        assert "runner.temp" in text


def test_manual_workflow_docs_describe_explicit_failure_guards() -> None:
    chinese = _read(ROOT / "README.md")
    english = _read(ROOT / "README.en.md")
    performance = _read(ROOT / "docs" / "performance.md")
    windows = _read(ROOT / "docs" / "windows-setup.md")
    quality = _read(ROOT / "docs" / "quality-report.md")
    audit = _read(ROOT / "docs" / "automated-test-audit-2026-07-22.md")
    certification = _read(ROOT / "docs" / "certification.md")
    all_docs = (chinese, english, performance, windows, quality, audit, certification)
    for text in all_docs:
        assert "refs/heads/main" in text
        assert "detached" in text.casefold()
    assert "显式失败" in chinese
    english_guard = english.casefold()
    assert (
        "fails explicitly with exit code 2" in english_guard
        or "explicitly rejects non-main dispatches" in english_guard
    )
    assert "dispatch-guard.log" in performance
    assert "status 2" in performance
    for text in (windows, quality, audit, certification):
        assert "needs: dispatch-guard" in text
        assert "status 2" in text
    assert "all-skipped" in audit
    for path in (ROOT / "README.md", ROOT / "README.en.md"):
        assert "actions/checkout" in _read(path)
    assert "actions/checkout" in certification


def test_docs_record_precheckout_and_run_attempt_licensed_isolation() -> None:
    paths = (
        ROOT / "README.md",
        ROOT / "README.en.md",
        ROOT / "docs" / "windows-setup.md",
        ROOT / "docs" / "quality-report.md",
        ROOT / "docs" / "automated-test-audit-2026-07-22.md",
        ROOT / "docs" / "certification.md",
    )
    for path in paths:
        text = _read(path)
        assert "licensed-aspen-certification" in text
        assert "expected_head_sha" in text
        assert "GITHUB_SHA" in text
        assert "GITHUB_RUN_ID" in text
        assert "GITHUB_RUN_ATTEMPT" in text
        assert "LICENSED_EVIDENCE_DIR" in text
        assert "github.run_attempt" in text
        assert "aspenops-licensed-artifact" in text
        assert "run-metadata.txt" in text
        assert "job_status" in text
        assert "runner.temp" in text
        assert "if-no-files-found: error" in text
        assert "serial" in text.casefold() or "串行" in text


def test_process_intent_docs_preserve_capability_boundaries() -> None:
    chinese = _read(ROOT / "README.md")
    english = _read(ROOT / "README.en.md")
    contract = _read(ROOT / "docs" / "process-intent-ir.md")
    integration = _read(ROOT / "docs" / "external-agent-integration.md")
    for text in (chinese, english, contract):
        assert "aspenops.flowsheet/v1" in text
        assert "DWSIM" in text
        assert "IDAES" in text
        assert "planned" in text
        assert "scripts/validate_process_ir.py" in text
        assert "process-ir-dashboard.html" in text
    assert "no adapter" in english.casefold()
    assert "未实现" in chinese
    assert "not copied source code" in integration.casefold()
    assert "proprietary prompts" in integration.casefold()


def test_environment_template_keeps_first_run_portable() -> None:
    text = _read(ROOT / ".env.example")
    assert "ASPENOPS_BACKEND=mock" in text
    assert "ASPENOPS_ALLOWED_ROOTS=\n" in text
    assert "ASPENOPS_STATE_DIR=var/aspenops-state" in text
    assert "# ASPENOPS_BACKEND=aspen_plus" in text
    assert "# ASPENOPS_ALLOWED_ROOTS=C:/AspenModels;C:/AspenResults" in text
    assert "# ASPENOPS_STATE_DIR=C:/AspenResults/aspenops-state" in text


def test_windows_guide_matches_hardened_bootstrap() -> None:
    text = _read(ROOT / "docs" / "windows-setup.md")
    assert "uv self update" in text
    assert "winget" in text
    assert "rechecks the actual version" in text
    assert "duplicate variables" in text.casefold()
    assert "unbalanced" in text.casefold()
    assert "without echoing raw" in text


def test_readmes_preserve_evidence_and_certification_boundaries() -> None:
    chinese = _read(ROOT / "README.md")
    english = _read(ROOT / "README.en.md")
    assert "已验证归档基线" in chinese
    assert "不是对任意后续提交的自动声明" in chinese
    assert "PENDING_REAL_ASPEN_CERTIFICATION" in chinese
    assert "archived validated baseline" in english.casefold()
    assert "not an automatic claim" in english.casefold()
    assert "PENDING_REAL_ASPEN_CERTIFICATION" in english
