from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_delivery_bundle_surface_is_documented_and_versioned() -> None:
    required = {
        "scripts/build_delivery_bundle.py",
        "tests/test_delivery_bundle.py",
        "docs/delivery-bundle.md",
        "docs/delivery-acceptance.md",
    }
    assert {path for path in required if not (ROOT / path).is_file()} == set()

    acceptance = (ROOT / "docs/delivery-acceptance.md").read_text(encoding="utf-8")
    bundle_guide = (ROOT / "docs/delivery-bundle.md").read_text(encoding="utf-8")
    for marker in (
        "scripts/build_delivery_bundle.py",
        "aspenops-handover-<sha12>.zip",
        "aspenops-sbom-<sha12>.spdx.json",
        "SHA256SUMS",
        "PENDING_REAL_ASPEN_CERTIFICATION",
    ):
        assert marker in acceptance
        assert marker in bundle_guide


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
    ):
        assert marker in source
