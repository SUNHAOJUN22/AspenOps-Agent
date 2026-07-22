from __future__ import annotations

from pathlib import Path

import pytest

from aspenops_nexus.batch import dry_run_document
from aspenops_nexus.config import Settings
from aspenops_nexus.policy import PolicyError


def real_request(allowed: Path) -> dict[str, object]:
    return {
        "backend": "aspen_plus",
        "model_path": str(allowed / "case.bkp"),
        "registry_path": str(allowed / "registry.json"),
        "points": [{}],
    }


def test_mock_settings_cannot_authorize_a_real_backend(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    settings = Settings(
        backend="mock",
        allowed_roots=(allowed.resolve(),),
        state_dir=allowed / "state",
    )

    with pytest.raises(PolicyError, match="must match ASPENOPS_BACKEND"):
        dry_run_document(real_request(allowed), settings)


def test_real_request_requires_explicit_allowed_roots(tmp_path: Path) -> None:
    settings = Settings(
        backend="aspen_plus",
        allowed_roots=(),
        state_dir=tmp_path / "state",
    )

    with pytest.raises(PolicyError, match="require ASPENOPS_ALLOWED_ROOTS"):
        dry_run_document(real_request(tmp_path), settings)
