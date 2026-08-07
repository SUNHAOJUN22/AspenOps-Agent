from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_delivery_bundle_surface_is_documented_and_versioned() -> None:
    required = {
        "scripts/build_delivery_bundle.py",
        "scripts/verify_delivery.py",
        "scripts/write_delivery_qualification.py",
        "tests/test_delivery_bundle.py",
        "tests/test_delivery_qualification_writer.py",
        "docs/delivery-bundle.md",
        "docs/delivery-acceptance.md",
        "README.md",
        "README.en.md",
    }
    assert {path for path in required if not (ROOT / path).is_file()} == set()

    acceptance = (ROOT / "docs/delivery-acceptance.md").read_text(encoding="utf-8")
    bundle_guide = (ROOT / "docs/delivery-bundle.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README.en.md").read_text(encoding="utf-8")

    common_markers = (
        "scripts/build_delivery_bundle.py",
        "aspenops-handover-<sha12>.zip",
        "aspenops-sbom-<sha12>.spdx.json",
        "SHA256SUMS",
        "PENDING_REAL_ASPEN_CERTIFICATION",
    )
    for marker in common_markers:
        assert marker in acceptance
        assert marker in bundle_guide
        assert marker in readme
        assert marker in readme_en

    assert "scripts/write_delivery_qualification.py" in acceptance
    assert "--require-current-qualification" in acceptance
    assert "--require-current-qualification" in readme
    assert "--require-current-qualification" in readme_en


def test_delivery_bundle_uses_deterministic_and_fail_closed_contracts() -> None:
    source = (ROOT / "scripts/build_delivery_bundle.py").read_text(encoding="utf-8")
    for marker in (
        "ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)",
        "allow_nan=False",
        "strict_timestamps=True",
        "normalized_file_mode",
        "SPDX-2.3",
        "PENDING_REAL_ASPEN_CERTIFICATION",
        "Symlink is not allowed",
        "output directory must be empty",
        "output path must be a directory",
        "source_date_epoch must be a non-negative integer",
        "source_sha does not match checked-out HEAD",
        "delivery source contains uncommitted files",
        "git_identity_verified",
        "GENERATED_CURRENT_QUALIFICATION",
    ):
        assert marker in source


def test_exact_tree_verifier_binds_git_commit_and_tree() -> None:
    source = (ROOT / "scripts/verify_delivery.py").read_text(encoding="utf-8")
    for marker in (
        '"HEAD"',
        '"HEAD^{tree}"',
        "current_qualification_source_mismatch",
        "current_qualification_tree_mismatch",
        "git_identity_unavailable",
    ):
        assert marker in source


def test_qualification_writer_is_acceptance_sized_and_fail_closed() -> None:
    source = (ROOT / "scripts/write_delivery_qualification.py").read_text(encoding="utf-8")
    for marker in (
        "MIN_PASSED_TESTS = 1200",
        "Final delivery qualification must not skip tests",
        "40-character lowercase hexadecimal Git SHA",
        "PENDING_REAL_ASPEN_CERTIFICATION",
        "Delivery verifier must report zero issues",
    ):
        assert marker in source
