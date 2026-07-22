from __future__ import annotations

from pathlib import Path

import pytest

from aspenops_nexus.cli import _controlled_path
from aspenops_nexus.config import Settings
from aspenops_nexus.policy import PolicyError


def test_cli_output_path_must_stay_inside_allowed_roots(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    settings = Settings(
        backend="aspen_plus",
        allowed_roots=(allowed,),
        state_dir=allowed / "state",
    )

    assert _controlled_path(allowed / "results.json", settings) == (
        allowed / "results.json"
    ).resolve()

    with pytest.raises(PolicyError, match="outside ASPENOPS_ALLOWED_ROOTS"):
        _controlled_path(tmp_path / "outside.json", settings)
