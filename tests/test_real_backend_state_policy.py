from __future__ import annotations

from pathlib import Path

import pytest

from aspenops_nexus.batch import dry_run_document
from aspenops_nexus.config import Settings
from aspenops_nexus.policy import PolicyError


def test_real_request_cannot_use_state_outside_allowed_roots(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    settings = Settings(
        backend="mock",
        allowed_roots=(allowed.resolve(),),
        state_dir=outside,
    )
    request = {
        "backend": "aspen_plus",
        "model_path": str(allowed / "case.bkp"),
        "registry_path": str(allowed / "registry.json"),
        "points": [{}],
    }

    with pytest.raises(PolicyError, match="state directory must be inside"):
        dry_run_document(request, settings)
